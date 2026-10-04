# 原创公开仓库开发约定

先读README、docs/MECHANISM.md和docs/VALIDATION.md。所有用户界面及项目说明使用简体中文。

- 内容主库为content/original-bank.json和content/campaign.json；用scripts/sync_public_content.py生成各端数据，保持完整字段。
- 公共题库家族为original。禁止导入教材题、教材扫描图、私人存档、真实AppID和访问凭据。
- Python使用XY_SHUATI_DATA_DIR隔离测试，正常原创版存档在独立目录；不清空用户进度。
- 共享财管数值/成长/经营代码修改时，同时核对miniprogram和ios-app的共享副本。精确十进制判定不能依赖BigInt幂的编译行为。
- 保存成功之后再扣款、领奖和显示结算；失败重试不能重抽或重复领取。
- 修改前保留可回退版本；执行scripts/check_public_release.py及受影响契约。Expo代码须执行typecheck、lint，按实际SDK版本查官方文档。
- 源码检查、实际构建、开发者工具、真机、GitHub CI、上传、审核和正式发布分别记录，未知项不填成功。
- 除非用户明确要求，不自动推送GitHub、上传小程序或开通付费服务。

