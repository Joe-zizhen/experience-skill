# 构建发布约定（合成项目）

当前部署版本为 v2。标准 pipeline 在发布前等待 CSS 编译完成，并通过临时文件替换发布 manifest。
workspace-link 模式下，链接工作区的 CSS 编译器独立运行；只有收到该次运行的 css-done 标记后，才能把“manifest 已发布”当作该次 CSS 可用于验证的条件。
旧维护分支仍使用 v1，v1 的 manifest 可能先于 CSS 写入；该分支的核验步骤仍需等待 css-done。
以上是本合成项目的契约，运行记录见任务报告；不代表真实生产实现。
