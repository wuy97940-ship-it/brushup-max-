# GitHub上传与协作

本目录是独立公开原创源码。上传前运行`python scripts/check_public_release.py`，检查`git status`和`git ls-files`；所有新增文件也需要扫描。教材、照片、存档、Cookie、私钥和账号配置使用自己的私有目录保存。

维护者先在自己的GitHub账号创建目标仓库，再设置真实仓库URL：

```sh
git remote add origin https://github.com/YOUR_ACCOUNT/xiaoyuan-adventure-public.git
git push -u origin main
```

若本机尚未初始化：运行`git init -b main`，检查并提交已通过扫描的源码。提交者身份使用自己的Git配置。已有提交历史不能只靠删除文件或新增.gitignore清理凭据；需要单独检查历史。

GitHub创建仓库、仓库可见性和实际推送需要维护者确定；本地检查不代表已上传或CI通过。仓库已有MIT许可证，保留版权与许可证原文；第三方依赖保留各自的许可。

公开仓库的反馈优先使用Issues，题目反馈带原创题号、科目、章节、正确计算过程与预期结果。不要提交学习备份、实名材料或联系资料。维护时采用分支及Pull Request，CI验证内容同步、公开扫描、独立答案模型、契约、类型检查和lint。

官方参考：[GitHub导入本地源码](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)、[Expo SDK57配置](https://docs.expo.dev/versions/v57.0.0/config/app/)。

