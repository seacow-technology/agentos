# Example .NET API Project

这是一个最小的 .NET 8 Web API 示例项目，用于测试 AgentOS 的 .NET Adapter。

## 结构

- `DotnetApi.csproj` - 项目文件
- `Program.cs` - 主入口
- `appsettings.json` - 配置文件

## 测试

```bash
# 注册项目
uv run agentos project add examples/dotnet-api --id dotnet-example

# 扫描项目
uv run agentos scan dotnet-example

# 查看生成的 FactPack
cat reports/dotnet-example/*/factpack.json
```
