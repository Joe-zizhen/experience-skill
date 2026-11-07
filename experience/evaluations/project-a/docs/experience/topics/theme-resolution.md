---
id: project-a/theme-resolution
scope: project:project-a
status: active
---

# 项目 A 的结算面板主题

当前认识：结算面板使用自身容器上的主题变量；改全局按钮变量不会改变面板背景。
适用条件：本合成项目的结算面板，当前源码结构。
如何使用：定位面板颜色时先检查 `src/theme.css` 的 `.checkout-panel` 与 `src/panel.css` 的变量消费。
依据与入口：当前项目 `src/theme.css`、`src/panel.css`。

## 必要现场

主题定义将 `--panel-surface` 绑定到容器，消费端用 `background: var(--panel-surface)`。这里只展示已经存在的映射，不声称已运行浏览器验证。
