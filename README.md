# changchun-experts · WorkBuddy 自建专家市场

一个可直接被 WorkBuddy「添加市场」消费的市场仓库。当前收录：

| 专家                                | 说明                                      | 版本    |
| --------------------------------- | --------------------------------------- | ----- |
| **长椿街执事**（nmpa-regulatory-expert） | NMPA 医疗器械法规专家：分类判定、注册申报、临床评价、体系核查、上市后合规 | 1.0.0 |

## 使用者怎么装（两种方式任选）

**方式一：一键安装（推荐，无需任何客户端设置）**

```bash
curl -fsSL https://codeload.github.com/PotusKing/workbuddy/tar.gz/refs/heads/main | tar xz -C /tmp && bash /tmp/workbuddy-main/install.sh
```

脚本会把专家包拷入本机专家目录并自动注册，重启 WorkBuddy 即可在专家列表看到「长椿街执事」。

**方式二：客户端添加市场**（若你的版本有该入口）

WorkBuddy → 连接器/插件管理 → **添加市场** → 填 `PotusKing/workbuddy` → 安装。

> 部分版本未放出「添加市场」入口，用方式一即可，效果相同。

## 维护者怎么更新

1. 改 `plugins/nmpa-regulatory-expert/` 里的内容
2. 更新两处版本号：本文件下方 `marketplace.json` 的 plugin `version`、专家自己的 `.codebuddy-plugin/plugin.json` 的 `version`
3. push 到 GitHub；客户端「刷新市场」即可拉到新版

## 发布前必做

- [ ] 把 `.codebuddy-plugin/marketplace.json` 里的 `REPLACE_WITH_YOUR_NAME` / `REPLACE_WITH_YOUR_EMAIL` 换成真实信息
- [ ] 确认要公开的内容边界：专家包内含沉淀的实务口径（qa-playbook 等），公开即授权他人使用
- [ ] 如只想给特定人群：GitHub 私有仓库 + 给对方 collaborator 权限，同样可被「添加市场」消费

## 结构说明

```
.codebuddy-plugin/marketplace.json   市场清单（客户端按此发现插件）
plugins/nmpa-regulatory-expert/      专家包（plugin.json + agents + skills + avatars）
```

与内置市场 `cb_teams_marketplace` 同构。
