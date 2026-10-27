# TB378FC Droidspaces 内核候选构建

仅适用于已记录的 TB378FC、ZUXOS 2.0.10.278、内核 6.6.82-android15-8-g076ac12bde16-ab13715361-4k。

这是尚未编译、尚未实机验证的构建工程，不是可刷机包。不要直接刷写 Image-UNTESTED。

## 输入与来源

- AOSP kernel_common：076ac12bde16ea0405a4ffd30404085b96b74eb5。
- Google Clang 18 r510928 / build 11368308：42d100b025eb5f4a41781348016c148e9e912cf9。
- SYSVIPC 补丁：Droidspaces-OSS 的 d0b3a2e1fac8d238f78119879811119be35d32f4，Documentation/resources/kernel-patches/GKI/below-kernel-6.12/001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch。
- stock.config、模块符号 CRC、BTF 布局及模块签名公钥，均来自本机备份。
- 只有公开证书，没有签名私钥。不会关闭模块版本或签名校验，也不会强制加载不兼容驱动。

## 构建方式

将目录内容上传到一个新的 GitHub 仓库根目录，包含 .github/workflows/build-kernel.yml。
进入 Actions，选择 Build TB378FC Droidspaces candidate，点击 Run workflow。
工作流仅支持手动运行，不自动发布、不连接平板、不刷写分区。

工作流先编译基础内核，并检查本机模块接口 CRC、BTF 核心结构布局和原厂证书是否兼容；基础检查不通过即停止。
通过后应用 SYSVIPC 的 ABI padding 补丁，启用 SYSVIPC、POSIX_MQUEUE、PID_NS、IPC_NS、USER_NS、DEVTMPFS，重新编译并重复检查，同时比较前后导出符号。
保留当前 CPU/PID 资源限制配置，不启用 CFS_BANDWIDTH、CGROUP_PIDS。

## 结果

下载 Actions 的 tb378fc-droidspaces-运行编号 工件。重点提供 build.log、baseline-compatibility.json、droidspaces-compatibility.json、SHA256SUMS。
全部静态检查通过后，仍需要重新打包本机启动镜像、确认恢复方式，才能安排设备测试。
当前 KernelSU 位于 init_boot_a；本工程不修改该分区。新内核的实际 KernelSU、触屏、网络、声音等兼容性仍需实机验证。

不要复用 TB375FC 的内核、证书、配置或刷写命令。
