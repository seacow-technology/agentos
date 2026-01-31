#!/usr/bin/env python3
"""
Gate: G_EX_SITE_STRUCTURE
验证最终产物必须包含 5 个 section（HTML 结构检查）
"""

import sys
from pathlib import Path
from html.parser import HTMLParser


class SectionParser(HTMLParser):
    """解析 HTML 找到所有 section"""
    
    def __init__(self):
        super().__init__()
        self.sections = []
    
    def handle_starttag(self, tag, attrs):
        if tag == "section":
            # 提取 id
            section_id = None
            for attr, value in attrs:
                if attr == "id":
                    section_id = value
                    break
            self.sections.append(section_id or "unnamed")


def check_site_structure(html_path: Path) -> bool:
    """检查 HTML 结构"""
    
    if not html_path.exists():
        print(f"❌ index.html not found: {html_path}")
        return False
    
    html_content = html_path.read_text()
    
    # 解析 HTML
    parser = SectionParser()
    parser.feed(html_content)
    
    # 必须的 sections
    required_sections = {"hero", "features", "architecture", "use-cases", "footer"}
    
    # 灵活匹配（允许下划线/连字符）
    found_sections = set()
    for section in parser.sections:
        section_normalized = section.lower().replace("_", "-")
        for req in required_sections:
            if req in section_normalized or section_normalized in req:
                found_sections.add(req)
    
    missing = required_sections - found_sections
    
    if missing:
        print(f"❌ Missing sections: {missing}")
        print(f"   Found: {found_sections}")
        return False
    
    print(f"✓ All required sections present: {found_sections}")
    return True


if __name__ == "__main__":
    # 查找 index.html
    possible_paths = [
        Path("index.html"),
        Path("demo_output/landing_site/index.html"),
        Path("outputs/landing_site/index.html")
    ]
    
    html_path = None
    for path in possible_paths:
        if path.exists():
            html_path = path
            break
    
    if not html_path:
        print("❌ index.html not found in expected locations")
        sys.exit(1)
    
    print(f"🔒 Gate G_EX_SITE_STRUCTURE")
    print(f"   Checking: {html_path}")
    print("=" * 60)
    
    if check_site_structure(html_path):
        print("=" * 60)
        print("✅ Gate G_EX_SITE_STRUCTURE PASSED")
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Gate G_EX_SITE_STRUCTURE FAILED")
        sys.exit(1)
