## 🎯 主要更新

- **新增 `inline_all_refs()` 函数**：完全展开所有 JSON Schema `$ref` 引用
- **修复兼容性问题**：解决 Gemini 2.5 Pro 和 Qwen3-max 无法处理嵌套 Pydantic 参数的问题
- **循环引用检测**：添加循环引用检测机制，防止无限递归
- **测试覆盖**：新增 9 个测试用例，确保功能稳定性

## 🔧 技术细节

- 所有 `$ref` 引用现在都会被完全展开为内联定义
- 生成的 JSON Schema 不再包含 `$defs` 或 `definitions` 部分
- 支持处理 `properties`、`items`、`anyOf`、`allOf` 等嵌套结构
- 兼容 OpenAI、Gemini、Qwen 等多种 LLM 模型

## 📦 安装

```bash
pip install openai-agents==0.2.6
```

## 🐛 修复的问题

- Gemini 2.5 Pro 将嵌套对象识别为字符串的问题
- Qwen3-max 在 `additionalProperties: false` + `$ref` 组合下序列化错误的问题

## 📝 完整更新日志

详见 [CHANGELOG.md](https://github.com/liuzhongyu-eagle/openai-agents-python-enhanced/blob/main/CHANGELOG.md)

## 🔗 相关链接

- **问题背景**：部分 LLM 模型无法正确处理 JSON Schema 中的 `$ref` 引用
- **解决方案**：完全展开所有引用，生成自包含的 JSON Schema
- **测试验证**：所有核心测试通过（46 个测试用例）

