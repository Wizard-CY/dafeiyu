# 本机路径覆盖（示例）· YunShan_You（悠云山）
# 把这个文件另存为同目录下的 paths.local.ps1，再按自己的机器改。
# 不改也能跑：start.ps1 会按注册表、PATH 和常见安装位置自动找 QQ。

# QQ NT 的 QQ.exe。只有自动探测找不到时才需要写。
$qqPath = 'D:\QQ\QQ.exe'
