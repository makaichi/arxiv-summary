<!--
 * @Author: Zerui Han <hanzr.nju@outlook.com>
 * @Date: 2025-06-24 11:29:48
 * @Description: 
 * @FilePath: /arxiv-summary/readme.zh.md
 * @LastEditTime: 2025-06-26 10:26:03
-->
# 使用 OpenAI 和飞书 Webhook 的 Arxiv 摘要工具

[English](readme.md)

本项目使用 OpenAI API 自动摘要指定主题类别中最新的 Arxiv 论文，并将摘要发送到飞书（Lark）webhook。它旨在通过 GitHub Actions 定期运行。

## 先决条件

在使用本项目之前，您需要满足以下条件：

1.  **OpenAI API 密钥：** 您需要一个 OpenAI 的 API 密钥才能使用他们的语言模型。请在 [OpenAI](https://platform.openai.com/) 创建账户并获取您的 API 密钥。

2.  **飞书 (Lark) Webhook URL：** 您需要在您的飞书群中创建一个传入 webhook 以接收摘要。请参阅飞书文档了解如何设置 webhook：[飞书自定义机器人](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot?lang=zh-CN)。**重要提示：** 确保您的 webhook 在飞书中具有向所需群组发布消息的必要权限。

## 设置说明

按照以下步骤设置 Arxiv 摘要工具：

1.  **Fork 仓库：** 点击此 GitHub 仓库右上角的“Fork”按钮，在您自己的 GitHub 账户中创建项目副本。

2.  **配置 GitHub Secrets：**

    *   转到您在 GitHub 上 Fork 的仓库页面。
    *   点击“Settings”选项卡。
    *   在左侧边栏中，点击“Security”，然后是“Secrets and variables”，最后是“Actions”。
    *   添加以下 secrets：
        *   **`OPENAI_API_KEY`：** 您的 OpenAI API 密钥。
        *   **`OPENAI_BASE_URL`：** (可选) API 端点的基本 URL。**重要提示：** 如果您正在使用代理、OpenAI 的不同端点或兼容 OpenAI 的 API 提供商（例如，[ModelScope](https://www.modelscope.cn/docs/model-service/API-Inference/intro)），则必须设置此变量。如果您使用的是标准 OpenAI API，请将其留空。
        *   **`WEBHOOK_URL`：** 您的飞书 webhook URL。

3.  **配置 GitHub Variables：**

    *   在相同的“Settings -> Security -> Secrets and variables -> Actions -> Variables”部分，添加以下变量：
        *   **`OPENAI_MODEL_NAME`：** 您希望用于摘要的 OpenAI 模型名称（例如，`gpt-3.5-turbo`，`gpt-4`）。请参阅 OpenAI 文档了解可用模型。
        *   **`SUMMARY_LANGUAGE`：** 您希望生成摘要的语言（例如，`English`，`Chinese`）。

4.  **配置工作流：**

    *   工作流文件 (`.github/workflows/eess.AS.yaml`) 已设置为每天 UTC 时间 00:02（北京时间 08:02）运行摘要工具。
    *   如果您想更改计划，请编辑 `.github/workflows/eess.AS.yaml` 文件中的 `cron` 表达式。请参阅 GitHub Actions 文档了解 cron 语法。
    *   **调度注意事项：** 请注意，GitHub Actions 的计划运行可能存在显著延迟。例如，原定于北京时间 08:02 运行的工作流可能要到 09:50 左右才会执行。此外，Arxiv 通常在北京时间 09:00 左右刷新其每日论文。因此，建议不要将计划设置得太早，以确保您摘要的是最新论文。

5.  **启用 GitHub Actions：** GitHub Actions 应该默认在您 Fork 的仓库中启用。如果未启用，请转到仓库的“Actions”选项卡并启用它们。

## 运行摘要工具

Arxiv 摘要工具将根据 `.github/workflows/eess.AS.yml` 文件中定义的计划自动运行。您也可以通过转到“Actions”选项卡，选择“Arxiv Summarizer”工作流，然后点击“Run workflow”来手动触发工作流运行。

## 自定义

*   **主题类别、用户兴趣和过滤级别：** 该脚本目前摘要 `eess.AS` 类别（音频和语音处理）的论文。您可以通过修改 `.github/workflows/eess.AS.yml` 文件中传递给 `arxiv_summarizer.py` 脚本的参数来更改此设置：

    ```yaml
        run: python arxiv_summarizer.py YOUR_CATEGORY --user_interest "您的兴趣" --filter_level "mid"
    ```

    *   将 `YOUR_CATEGORY` 替换为所需的 Arxiv 主题类别代码（例如，`cs.AI`，`math.ST`）。请参阅 Arxiv 文档了解可用类别列表。
    *   使用 `--user_interest` 指定您的特定兴趣领域（例如，`"机器学习, 自然语言处理"`）。如果提供，论文将根据相关性进行评分和排序。如果省略，所有论文的相关性将为 0。
    *   使用 `--filter_level` 根据相关性过滤论文。选项包括 `"low"`（分数 >=0）、`"mid"`（分数 >=1）、`"high"`（分数 >=2）或 `"none"`（不进行过滤）。如果设置了过滤级别，则只有相关性高于或等于指定级别的论文才会被摘要。这可以通过避免摘要不相关的论文来节省 token。

## 重要提示

*   **成本：** 使用 OpenAI API 可能会产生费用。请监控您的 OpenAI API 使用情况并设置账单提醒，以避免意外费用。

*   **速率限制：** Arxiv 网站和 OpenAI API 可能有速率限制。脚本应该能够优雅地处理速率限制，但如果遇到错误，您可能需要调整请求频率。

*   **错误处理：** 脚本包含基本的错误处理，但您可能需要为生产环境添加更健壮的错误处理。

*   **安全性：** 不要在代码中硬编码您的 API 密钥或 webhook URL。始终使用 GitHub Secrets 来存储敏感信息。

*   **Arxiv 使用：** 请遵守 Arxiv 的使用政策，避免过度抓取。