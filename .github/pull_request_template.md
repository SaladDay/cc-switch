## Summary / 概述

<!-- Briefly describe what this PR does and why. / 简要描述这个 PR 做了什么以及为什么。 -->

## Related Issue / 关联 Issue

<!-- Link the related issue. Use "Fixes #123" to auto-close it when merged. -->
<!-- 关联相关 Issue。使用 "Fixes #123" 可在合并时自动关闭。 -->

Fixes #

## Contribution Policy / 贡献政策

<!-- If this change requires prior discussion, link the Issue above and verify the approval signal before implementation. / 如本次改动需要事先讨论，请在上方关联 Issue，并在开始实现前确认批准信号。 -->

- [ ] If prior confirmation is required, the related Issue has a `contribution-approved` label or an explicit maintainer confirmation / 如需事先确认，关联 Issue 已有 `contribution-approved` 标签或维护者明确确认
- [ ] This PR stays within the confirmed scope and non-goals / 本 PR 未超出已确认的范围和非目标

## Screenshots / 截图

<!-- If applicable, add before/after screenshots. / 如有需要，请添加修改前后的截图。 -->

| Before / 修改前 | After / 修改后 |
|-----------------|---------------|
|                 |               |

## Checklist / 检查清单

- [ ] `pnpm typecheck` passes / 通过 TypeScript 类型检查
- [ ] `pnpm format:check` passes / 通过代码格式检查
- [ ] `pnpm test:unit` passes (if frontend or runtime behavior changed) / `pnpm test:unit` 通过（如修改了前端或运行时行为）
- [ ] `cargo clippy` passes (if Rust code changed) / 通过 Clippy 检查（如修改了 Rust 代码）
- [ ] `cargo test` passes (if Rust code changed) / `cargo test` 通过（如修改了 Rust 代码）
- [ ] Updated i18n files if user-facing text changed / 如修改了用户可见文本，已更新国际化文件
