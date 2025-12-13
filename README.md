# Java JAR 反编译工具集

一个用于批量反编译 Java JAR 文件并智能分类的工具集合。

## 项目概述

本项目包含两个主要工具：

1. **class2java.py** - 批量反编译 JAR 文件
2. **selectmvn.py** - 智能分类 JAR 文件（区分公共库和私有库）

## 功能特性

### class2java.py（批量反编译）
- 使用 CFR 反编译器批量处理 JAR 文件
- 支持多线程并发处理（最大5个工作线程）
- 自动创建输出目录结构
- 命令行参数简单易用

### selectmvn.py（智能分类）
- 智能识别 JAR 文件类型（公共库 vs 私有库）
- 基于 Maven Central 仓库验证
- 支持多线程高速处理（最大60个工作线程）
- 详细的分类报告和统计
- 可提取私有库到指定目录

## 环境要求

- Python 3.6+
- Java 运行环境（用于 CFR 反编译器）
- 网络连接（用于 Maven Central 验证）

## 依赖库

```bash
pip install requests urllib3
```

## 使用方法

### 1. 批量反编译 JAR 文件

```bash
python class2java.py <JAR文件目录> <输出目录>
```

示例：
```bash
python class2java.py ./jars ./output
```

### 2. 智能分类 JAR 文件

基本使用：
```bash
python selectmvn.py <JAR文件目录>
```

提取私有库到指定目录：
```bash
python selectmvn.py <JAR文件目录> -o ./private_libs
```

## 分类规则

### 公共库识别
工具通过以下方式识别公共库：
- 已知公共库前缀匹配（Spring、Apache Commons、SLF4J 等）
- Maven Central 仓库验证
- POM 文件中的坐标信息验证

### 私有库识别
- 不符合公共库特征的文件
- 无法通过 Maven Central 验证的文件
- 公司/组织内部开发的库

## 输出说明

### class2java.py 输出
- 每个 JAR 文件生成独立的输出目录
- 反编译后的 Java 源代码保持原始包结构

### selectmvn.py 输出
- 控制台显示详细的分类过程
- ✅ 表示公共库
- ❌ 表示私有库
- 显示具体的 Maven 坐标信息

## 性能优化

- 多线程并发处理
- HTTP 连接池复用
- 智能重试机制
- 请求超时控制

## 注意事项

1. 确保网络连接正常（Maven Central 验证需要）
2. 对于大型 JAR 文件集合，处理时间可能较长
3. 私有库分类结果需要人工复核确认
4. 反编译后的代码仅供学习和分析使用

## 项目结构

```
Java-Decompile-AllJar-main/
├── README.md          # 项目说明文档
├── cfr-0.152.jar      # CFR 反编译器
├── class2java.py      # 批量反编译脚本
└── selectmvn.py       # JAR 分类脚本
```

## 许可证

本项目仅供学习和研究使用，请遵守相关法律法规。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进项目。