"""Stock query parsing and descriptive price-action analysis.

Design constraints for Chat stock-analysis path:
1. Only describe what already happened in past candles (N bars lookback).
2. No prediction, no recommendation, no valuation/emotional judgement.
3. Style must be neutral and descriptive ("market microscope / recorder").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from octopusos.core.chat.router_priority_contract import reserved_stock_symbol_stopwords


STOCK_DISCLAIMER = "以下仅为对已发生走势的描述（不预测、不建议、不评价）。"
STOCK_REFUSAL_TEMPLATE = (
    "我可以继续描述已发生走势与结构变化，但不提供买卖建议或未来判断。"
    "你要我把近 N 根的高低点/区间/波动细化一下吗？"
)
STOCK_FOLLOWUP_PROMPT = "你想看：近 20 / 60 / 120 根？日线 or 1 小时线？"

_TIMEFRAME_PATTERNS = (
    ("4H", (r"\b4h\b", r"4小时", r"4 小时", r"4小时线")),
    ("1H", (r"\b1h\b", r"1小时", r"1 小时", r"小时线", r"\bhourly\b")),
    ("1W", (r"\b1w\b", r"周线", r"\bweekly\b")),
    ("1D", (r"\b1d\b", r"日线", r"\bdaily\b")),
)

_SYMBOL_ALIASES = {
    "苹果": "AAPL",
    "apple": "AAPL",
    "特斯拉": "TSLA",
    "tesla": "TSLA",
    "英伟达": "NVDA",
    "nvidia": "NVDA",
    "微软": "MSFT",
    "microsoft": "MSFT",
    "谷歌": "GOOGL",
    "google": "GOOGL",
    "亚马逊": "AMZN",
    "amazon": "AMZN",
    "腾讯": "0700.HK",
    "阿里": "9988.HK",
    "茅台": "600519.SS",
}

_BANNED_TOKENS = [
    "建议",
    "可以买",
    "卖出",
    "止损",
    "止盈",
    "仓位",
    "大概率",
    "预计",
    "将会",
    "会涨",
    "会跌",
    "目标价",
    "抄底",
    "逃顶",
    "风险很大",
    "值得",
    "不值得",
    "强势",
    "弱势",
    "利好",
    "利空",
    "意味着",
    "预示",
    "可能",
    "很可能",
    "买点",
    "卖点",
]

_MARKET_CCY = {
    "US": "USD",
    "HK": "HKD",
    "CN": "CNY",
}


@dataclass(frozen=True)
class StockQuery:
    symbol: str
    market: str
    timeframe: str
    lookback: int
    parse_note: str = ""


class StockDataError(RuntimeError):
    """Raised when stock OHLCV data cannot be fetched or parsed."""


def is_stock_query(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    if any(token in lowered for token in ("weather", "forecast", "天气", "温度", "气温")):
        return False
    fx_pair_pattern = r"(?<![A-Za-z])[A-Za-z]{3}\s*(?:/|to|->|兑|对|-)\s*[A-Za-z]{3}(?![A-Za-z])"
    if re.search(fx_pair_pattern, text, re.IGNORECASE) and not any(t in lowered for t in ("股票", "股价", "stock")):
        return False
    if any(token in lowered for token in ("汇率", "currency", "exchange rate", " fx ")):
        return False
    if _extract_symbol(text):
        return True
    tokens = ("股票", "股价", "k线", "走势", "日线", "周线", "candles", "price action", "ticker")
    return any(t in lowered for t in tokens)


def is_trade_advice_request(text: str) -> bool:
    lowered = (text or "").lower()
    advice_patterns = (
        r"能买吗",
        r"可以买吗",
        r"要不要买",
        r"怎么操作",
        r"买入",
        r"卖出",
        r"止损",
        r"止盈",
        r"仓位",
        r"目标价",
        r"抄底",
        r"逃顶",
        r"\bshould i buy\b",
        r"\bshould i sell\b",
        r"\bbuy or sell\b",
    )
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in advice_patterns)


def parse_stock_query(text: str) -> Optional[StockQuery]:
    if not is_stock_query(text):
        return None
    symbol_raw = _extract_symbol(text)
    if not symbol_raw:
        return None
    market = _infer_market(symbol_raw)
    parse_note = ""
    if market == "US" and "." in symbol_raw and symbol_raw.endswith(".US"):
        symbol_raw = symbol_raw[:-3]
    if market == "UNKNOWN":
        market = "US"
        parse_note = "未能确定市场，按数据源规则默认解析为 US。"

    symbol = _normalize_symbol(symbol_raw, market)
    timeframe = _parse_timeframe(text)
    lookback = _parse_lookback(text)
    return StockQuery(symbol=symbol, market=market, timeframe=timeframe, lookback=lookback, parse_note=parse_note)


def describe_price_action(candles: List[Dict[str, Any]], options: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    options = options or {}
    timeframe = str(options.get("timeframe") or "1D")
    price_unit = str(options.get("price_unit") or "").strip().upper()
    def fmt_price(v: float) -> str:
        return f"{v:.2f} {price_unit}".strip()
    def fmt_abs(v: float) -> str:
        return f"{v:.2f} {price_unit}".strip()
    n = len(candles)
    if n == 0:
        return {
            "overview": "样本为空，无法描述区间变化。",
            "structure": "样本为空，无法描述结构特征。",
            "volatility": "样本为空，无法描述 K 线与波动特征。",
            "volume": "成交量数据不可用。",
        }

    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    opens = [float(c["open"]) for c in candles]
    start_close = closes[0]
    end_close = closes[-1]
    period_high = max(highs)
    period_low = min(lows)
    delta_pct = ((end_close - start_close) / start_close * 100.0) if start_close else 0.0

    if delta_pct > 2.0:
        direction = "整体抬升"
    elif delta_pct < -2.0:
        direction = "整体回落"
    else:
        direction = "区间震荡"

    range_pct = ((period_high - period_low) / start_close * 100.0) if start_close else 0.0
    overview = (
        f"过去 {n} 根 {timeframe} 内，价格运行区间为 {fmt_price(period_low)} 到 {fmt_price(period_high)}，"
        f"区间振幅约 {range_pct:.2f}%；收盘由 {start_close:.2f} 变化到 {end_close:.2f}，"
        f"在回看区间内呈现 {direction}。"
    )
    if n < 20:
        overview += "样本较少，仅描述可见变化。"

    hh = sum(1 for i in range(1, n) if highs[i] > highs[i - 1])
    hl = sum(1 for i in range(1, n) if lows[i] > lows[i - 1])
    lh = sum(1 for i in range(1, n) if highs[i] < highs[i - 1])
    ll = sum(1 for i in range(1, n) if lows[i] < lows[i - 1])
    if hh > lh and hl > ll:
        structure_state = "高点与低点有阶段性抬高"
    elif hh < lh and hl < ll:
        structure_state = "高点与低点有阶段性下移"
    else:
        structure_state = "高低点交替，结构更接近震荡"
    channel_width_pct = ((period_high - period_low) / end_close * 100.0) if end_close else 0.0
    window_states = []
    for window in (5, 20, 60):
        if n < window:
            continue
        w_closes = closes[-window:]
        w_start = w_closes[0]
        w_end = w_closes[-1]
        w_delta_pct = ((w_end - w_start) / w_start * 100.0) if w_start else 0.0
        w_high = max(highs[-window:])
        w_low = min(lows[-window:])
        window_states.append(
            f"{window}根区间 {fmt_price(w_low)}-{fmt_price(w_high)}，收盘变动 {w_delta_pct:.2f}%"
        )
    window_text = "；".join(window_states) if window_states else "窗口样本不足，未展开多窗口拆分"
    structure = (
        f"在过去 {n} 根内，价格结构显示 {structure_state}；"
        f"当前通道宽度约为收盘的 {channel_width_pct:.2f}%。"
        f"多窗口拆分：{window_text}。"
    )

    recent = candles[-min(5, n) :]
    long_upper = 0
    long_lower = 0
    small_body = 0
    gaps = 0
    for idx, c in enumerate(recent):
        o = float(c["open"])
        h = float(c["high"])
        l = float(c["low"])
        cl = float(c["close"])
        body = abs(cl - o)
        span = max(h - l, 1e-9)
        upper = h - max(o, cl)
        lower = min(o, cl) - l
        if upper >= max(body * 2.0, span * 0.35):
            long_upper += 1
        if lower >= max(body * 2.0, span * 0.35):
            long_lower += 1
        if (body / span) <= 0.2:
            small_body += 1
        if idx > 0:
            prev = recent[idx - 1]
            prev_h = float(prev["high"])
            prev_l = float(prev["low"])
            if l > prev_h or h < prev_l:
                gaps += 1

    true_ranges = [float(c["high"]) - float(c["low"]) for c in candles]
    tr_mean = sum(true_ranges) / len(true_ranges)
    tr_recent = true_ranges[-min(10, len(true_ranges)) :]
    tr_recent_mean = sum(tr_recent) / len(tr_recent)
    tr_ratio = (tr_recent_mean / tr_mean) if tr_mean else 1.0
    if tr_ratio > 1.15:
        vol_regime = "短窗波动高于样本均值"
    elif tr_ratio < 0.85:
        vol_regime = "短窗波动低于样本均值"
    else:
        vol_regime = "短窗波动接近样本均值"
    volatility = (
        f"最近 {len(recent)} 根里，出现 {long_upper} 次长上影、{long_lower} 次长下影、"
        f"{small_body} 次实体偏小，跳空出现 {gaps} 次；"
        f"近端平均高低波幅约 {fmt_abs(tr_recent_mean)}，样本平均约 {fmt_abs(tr_mean)}，{vol_regime}。"
    )
    indicator_state = _build_indicator_state(closes)
    if indicator_state:
        volatility += f"指标状态（仅记录）：{indicator_state}"

    volume_values = [c.get("volume") for c in candles]
    usable_volumes = [float(v) for v in volume_values if v is not None]
    if not usable_volumes:
        volume = "成交量数据不可用。"
    else:
        recent_count = min(5, len(usable_volumes))
        recent_mean = sum(usable_volumes[-recent_count:]) / recent_count
        base_mean = sum(usable_volumes) / len(usable_volumes)
        ratio = (recent_mean / base_mean) if base_mean else 1.0
        if ratio > 1.15:
            vol_state = "相对近段均值放大"
        elif ratio < 0.85:
            vol_state = "相对近段均值减小"
        else:
            vol_state = "接近近段均值"
        missing_count = sum(1 for v in volume_values if v is None)
        missing_hint = f"（其中 {missing_count} 根无成交量）" if missing_count else ""
        volume = (
            f"成交量显示最近 {recent_count} 根均值约为 {recent_mean:.0f}，"
            f"整体均值约为 {base_mean:.0f}，当前 {vol_state}{missing_hint}。"
        )

    return {
        "overview": overview,
        "structure": structure,
        "volatility": volatility,
        "volume": volume,
    }


def analysis_lint(text: str) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for token in _BANNED_TOKENS:
        for match in re.finditer(re.escape(token), text):
            if token == "建议" and match.start() > 0 and text[match.start() - 1] == "不":
                continue
            if token in {"可能", "很可能"}:
                context = text[max(0, match.start() - 8) : min(len(text), match.end() + 12)]
                if "数据缺失" in context or "数据不可用" in context:
                    continue
            violations.append(
                {
                    "token": token,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return violations


def sanitize_analysis_text(text: str) -> str:
    parts = re.split(r"(?<=[。！？\n])", text)
    cleaned_parts: List[str] = []
    for part in parts:
        if not part.strip():
            continue
        if analysis_lint(part):
            continue
        cleaned_parts.append(part)
    return "".join(cleaned_parts).strip()


def build_stock_response_text(
    *,
    sections: Dict[str, str],
    include_followup: bool = True,
    parse_note: str = "",
) -> str:
    lines = [
        STOCK_DISCLAIMER,
        "",
        f"1. 区间概览：{sections.get('overview', '')}",
        f"2. 结构特征：{sections.get('structure', '')}",
        f"3. 波动与 K 线形态：{sections.get('volatility', '')}",
        f"4. 成交量：{sections.get('volume', '')}",
    ]
    if parse_note:
        lines.append(f"补充：{parse_note}")
    if include_followup:
        lines.extend(["", STOCK_FOLLOWUP_PROMPT])
    return "\n".join(lines).strip()


def build_numeric_summary_mode(
    *,
    candles: List[Dict[str, Any]],
    timeframe: str,
    symbol: str,
    price_unit: str = "",
    parse_note: str = "",
) -> str:
    if not candles:
        text = (
            f"{STOCK_DISCLAIMER}\n\n"
            f"{symbol} 暂无可用 {timeframe} 数据，未生成走势段落。\n\n"
            f"{STOCK_FOLLOWUP_PROMPT}"
        )
        return text
    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    n = len(candles)
    first = closes[0]
    last = closes[-1]
    pct = ((last - first) / first * 100.0) if first else 0.0
    lines = [
        STOCK_DISCLAIMER,
        "",
        f"{symbol} 过去 {n} 根 {timeframe} 数据摘要：",
        f"- 高点：{max(highs):.2f} {price_unit}".strip(),
        f"- 低点：{min(lows):.2f} {price_unit}".strip(),
        f"- 首收：{first:.2f} {price_unit}".strip(),
        f"- 末收：{last:.2f} {price_unit}".strip(),
        f"- 区间涨跌幅：{pct:.2f}%",
    ]
    if parse_note:
        lines.append(f"- 补充：{parse_note}")
    lines.extend(["", STOCK_FOLLOWUP_PROMPT])
    return "\n".join(lines)


class YahooOHLCVProvider:
    """Minimal Yahoo chart adapter that returns unified OHLCV candles."""

    _BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def fetch(self, query: StockQuery) -> Dict[str, Any]:
        interval = "1h" if query.timeframe in {"1H", "4H"} else "1d" if query.timeframe == "1D" else "1wk"
        range_arg = self._range_for(query.timeframe, query.lookback)
        url = f"{self._BASE_URL}{query.symbol}?{urlencode({'interval': interval, 'range': range_arg, 'events': 'history'})}"
        request = Request(url, headers={"User-Agent": "AgentOS/stock-query"})
        try:
            with urlopen(request, timeout=12) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise StockDataError(f"Failed to fetch market data: {exc}") from exc

        candles = self._parse_chart_payload(payload)
        if query.timeframe == "4H":
            candles = self._aggregate_4h(candles)
        candles = candles[-query.lookback :]
        return {
            "symbol": query.symbol,
            "market": query.market,
            "timeframe": query.timeframe,
            "candles": candles,
        }

    @staticmethod
    def _range_for(timeframe: str, lookback: int) -> str:
        if timeframe == "1H":
            return "3mo" if lookback > 120 else "1mo"
        if timeframe == "4H":
            return "6mo"
        if timeframe == "1W":
            return "10y"
        return "5y" if lookback > 240 else "1y"

    @staticmethod
    def _parse_chart_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        chart = payload.get("chart") if isinstance(payload, dict) else None
        error = chart.get("error") if isinstance(chart, dict) else None
        if error:
            raise StockDataError(str(error))
        result = (chart.get("result") or [None])[0] if isinstance(chart, dict) else None
        if not isinstance(result, dict):
            raise StockDataError("Chart result missing")
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") if isinstance(result.get("indicators"), dict) else {}
        quote = (indicators.get("quote") or [None])[0] if isinstance(indicators, dict) else None
        if not isinstance(quote, dict):
            raise StockDataError("Quote payload missing")
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []
        candles: List[Dict[str, Any]] = []
        for i, ts in enumerate(timestamps):
            try:
                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]
            except Exception:
                continue
            if None in (o, h, l, c):
                continue
            v = volumes[i] if i < len(volumes) else None
            iso_ts = datetime.fromtimestamp(int(ts), tz=UTC).isoformat().replace("+00:00", "Z")
            candles.append(
                {
                    "ts": iso_ts,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v) if v is not None else None,
                }
            )
        if not candles:
            raise StockDataError("No valid candles")
        return candles

    @staticmethod
    def _aggregate_4h(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: List[Dict[str, Any]] = []
        bucket: List[Dict[str, Any]] = []
        for candle in candles:
            bucket.append(candle)
            if len(bucket) < 4:
                continue
            grouped.append(_aggregate_bucket(bucket))
            bucket = []
        if bucket:
            grouped.append(_aggregate_bucket(bucket))
        return grouped


def _aggregate_bucket(bucket: List[Dict[str, Any]]) -> Dict[str, Any]:
    volumes = [float(c["volume"]) for c in bucket if c.get("volume") is not None]
    return {
        "ts": str(bucket[-1]["ts"]),
        "open": float(bucket[0]["open"]),
        "high": max(float(c["high"]) for c in bucket),
        "low": min(float(c["low"]) for c in bucket),
        "close": float(bucket[-1]["close"]),
        "volume": sum(volumes) if volumes else None,
    }


def _extract_symbol(text: str) -> Optional[str]:
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    for alias, symbol in _SYMBOL_ALIASES.items():
        if alias in lowered:
            return symbol
    cn_hk = re.search(r"\b(\d{1,6}\.(?:HK|SS|SZ))\b", raw, re.IGNORECASE)
    if cn_hk:
        return cn_hk.group(1).upper()
    us = re.search(r"\b([A-Za-z]{1,6}(?:\.[A-Za-z]{1,3})?)\b", raw)
    if us:
        token = us.group(1)
        stop_words = {"trend", "stock", "price", "query", "line", "today", "lookback"}
        stop_words.update(reserved_stock_symbol_stopwords())
        if token.lower() not in stop_words:
            return token.upper()
    hk_digits = re.search(r"\b(\d{1,4})\s*(?:港股|hk)\b", raw, re.IGNORECASE)
    if hk_digits:
        return f"{hk_digits.group(1)}.HK"
    return None


def _infer_market(symbol: str) -> str:
    sym = symbol.upper()
    if sym.endswith(".HK"):
        return "HK"
    if sym.endswith(".SS") or sym.endswith(".SZ"):
        return "CN"
    if re.fullmatch(r"[A-Z]{1,6}", sym):
        return "US"
    return "UNKNOWN"


def infer_price_unit(market: str) -> str:
    return _MARKET_CCY.get(str(market or "").upper(), "USD")


def _normalize_symbol(symbol: str, market: str) -> str:
    sym = symbol.upper()
    if market == "HK":
        m = re.fullmatch(r"(\d{1,4})(?:\.HK)?", sym)
        if m:
            return f"{int(m.group(1)):04d}.HK"
    if market == "CN":
        m = re.fullmatch(r"(\d{6})(?:\.(SS|SZ))?", sym)
        if m:
            suffix = m.group(2) or "SS"
            return f"{m.group(1)}.{suffix}"
    if market == "US":
        return sym.replace(".US", "")
    return sym


def _parse_timeframe(text: str) -> str:
    lowered = (text or "").lower()
    for frame, patterns in _TIMEFRAME_PATTERNS:
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
            return frame
    return "1D"


def _parse_lookback(text: str) -> int:
    lowered = (text or "").lower()
    patterns = (
        r"(?:近|最近|过去|last|past)\s*(\d{1,4})\s*(?:根|天|日|小时|周|k|candles?|bars?)",
        r"(\d{1,4})\s*(?:根|candles?|bars?)",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            try:
                value = int(match.group(1))
                return max(1, min(600, value))
            except Exception:
                continue
    return 60


def _build_indicator_state(closes: List[float]) -> str:
    ma20 = _simple_ma(closes, 20)
    ma60 = _simple_ma(closes, 60)
    rsi14 = _rsi(closes, 14)
    macd_hist_now, macd_hist_prev = _macd_hist_pair(closes)
    states: List[str] = []
    latest = closes[-1] if closes else 0.0
    if ma20 is not None:
        relation20 = "上方" if latest >= ma20 else "下方"
        states.append(f"收盘位于 MA20 {relation20}")
    if ma60 is not None:
        relation60 = "上方" if latest >= ma60 else "下方"
        states.append(f"收盘位于 MA60 {relation60}")
    if rsi14 is not None:
        states.append(f"RSI14 约为 {rsi14:.1f}")
    if macd_hist_now is not None and macd_hist_prev is not None:
        if abs(macd_hist_now) > abs(macd_hist_prev):
            states.append("MACD 柱体绝对值较前一根扩大")
        elif abs(macd_hist_now) < abs(macd_hist_prev):
            states.append("MACD 柱体绝对值较前一根缩小")
        else:
            states.append("MACD 柱体绝对值与前一根接近")
    return "；".join(states)


def _simple_ma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def _rsi(values: List[float], period: int) -> Optional[float]:
    if len(values) <= period:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    ema_values = [values[0]]
    for price in values[1:]:
        ema_values.append(price * k + ema_values[-1] * (1.0 - k))
    return ema_values


def _macd_hist_pair(values: List[float]) -> tuple[Optional[float], Optional[float]]:
    if len(values) < 35:
        return None, None
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    macd_line = [a - b for a, b in zip(ema12, ema26)]
    signal = _ema(macd_line, 9)
    hist = [m - s for m, s in zip(macd_line, signal)]
    if len(hist) < 2:
        return None, None
    return hist[-1], hist[-2]
