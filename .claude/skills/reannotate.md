---
description: Reannotate Python code with fresh, clear comments. Removes all existing comments and adds comprehensive new documentation for specified files or classes.
arguments:
  - name: target
    description: File path or class name to reannotate (e.g., "/path/to/file.py" or "TMDbClient")
    required: true
---

# Reannotate Code Comments

You are tasked with reannotating Python code with fresh, clear, comprehensive comments.

## Trigger Detection

This skill should be invoked when users say things like:
- "重写一下注释" (Rewrite the comments)
- "重新标注注释" (Reannotate comments)
- "添加注释" (Add comments)
- "给文件加注释" (Add comments to file)
- Combined with a file path or class name

## Instructions

1. **Parse the target**:
   - If `{{target}}` is a file path (ends with .py), use that file directly
   - If `{{target}}` is a class name, search for files containing that class
   - If no path specified and searching for class, search in `backend/` directory first

2. **Analyze the code thoroughly**:
   - Read the entire file
   - Understand the class purpose, methods, and logic
   - Identify what each method does
   - Note important implementation details

3. **Remove all existing comments**:
   - Delete all single-line comments (`# ...`)
   - Delete all docstrings (`"""..."""` or `'''...'''`)
   - Keep the code structure intact

4. **Add fresh, clear comments**:
   - Add a comprehensive module-level docstring explaining the file's purpose
   - Add a detailed class docstring covering:
     - Purpose and responsibility
     - Key attributes
     - Usage example (if applicable)
   - For each method, add:
     - A clear docstring with purpose description
     - Args section documenting parameters
     - Returns section documenting return values
     - Raises section for exceptions (if any)
     - Inline comments for complex logic

5. **Comment quality standards**:
   - **必须使用中文注释** (All comments MUST be in Chinese)
   - Use clear, concise language
   - Focus on WHY, not just WHAT
   - Document non-obvious implementation details
   - Include usage examples for public APIs
   - Follow Google docstring style or PEP 257
   - **对于异步方法**：不在 Example 中直接写 await 语法，避免语法错误。使用以下方式之一：
     * 只展示方法调用签名（不含 await）
     * 使用伪代码格式说明用法
     * 用注释标记"异步调用"

6. **Preserve code functionality**:
   - Do NOT change any logic or implementation
   - Only remove/add comments and docstrings
   - Maintain proper indentation

## Example Output Format

### 同步方法示例模板

```python
"""
模块功能简述。

模块详细说明，描述该模块的主要功能和用途。
"""

from typing import Optional


class ClassName:
    """类的简短描述。

    类的详细说明，描述类的职责、用途和关键特性。

    Attributes:
        attr1 (type): 属性1的说明
        attr2 (type): 属性2的说明

    Example:
        >>> obj = ClassName(param1="value1")
        >>> result = obj.method_name(arg1, arg2)
        >>> print(result)
    """

    def __init__(self, param1: str, param2: int = 0):
        """初始化类实例。

        Args:
            param1: 参数1说明
            param2: 参数2说明，默认值说明
        """
        self.param1 = param1
        self.param2 = param2
        # 初始化其他属性
        self._cache = {}

    def method_name(self, arg1: str, arg2: Optional[int] = None) -> dict:
        """方法功能简述。

        方法详细说明，描述方法的作用、实现逻辑和注意事项。

        Args:
            arg1: 参数1说明
            arg2: 参数2说明，可选

        Returns:
            返回值说明

        Raises:
            ValueError: 异常条件说明
            ConnectionError: 异常条件说明
        """
        # 实现逻辑说明
        if arg2:
            return {"key": "value"}
        return {}
```

### 异步方法示例模板

```python
"""
模块功能简述。

模块详细说明。
"""

from typing import Dict


class AsyncService:
    """异步服务类的简短描述。

    类的详细说明，描述类的职责和用途。

    Attributes:
        dependency (type): 依赖组件说明

    Example:
        >>> service = AsyncService(dependency=dep)
        >>> # 在异步上下文中调用
        >>> # result = await service.async_method(
        >>> #     param1="value1",
        >>> #     param2="value2"
        >>> # )
    """

    def __init__(self, *, dependency: DependencyType) -> None:
        """初始化异步服务。

        Args:
            dependency: 依赖组件说明
        """
        self._dependency = dependency

    async def async_method(
        self,
        *,
        param1: str,
        param2: str,
        param3: bool = True,
    ) -> Dict[str, str]:
        """异步方法功能简述。

        方法详细说明，描述异步操作的用途和流程。

        Args:
            param1: 参数1说明
            param2: 参数2说明
            param3: 参数3说明，默认 True

        Returns:
            返回值说明

        Raises:
            ValueError: 异常条件说明
            ConnectionError: 异常条件说明

        Note:
            注意事项，可以包含重要的使用说明或限制条件
        """
        # 实现逻辑说明
        return await self._dependency.process(
            param1=param1,
            param2=param2,
            param3=param3,
        )
```

## Process

1. **Identify the target**:
   - If `{{target}}` is a file path, read that file directly
   - If `{{target}}` is a class name, use Grep to find files containing `class {{target}}`
   - If multiple files found, ask user which one to process

2. **Read and analyze**:
   - Read the entire file to understand its structure
   - Identify all classes, functions, and their purposes
   - Note complex logic that needs inline comments

3. **Reannotate**:
   - Remove all existing comments and docstrings
   - Add fresh, comprehensive documentation following the quality standards
   - Use Edit tool to make the changes

4. **Verify**:
   - Ensure all comments follow the quality standards above
   - Verify no code logic was changed
   - Check that indentation is preserved

Begin by identifying the target file and analyzing its code.
