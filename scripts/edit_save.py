#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改 金币 + 四个资源，重新 XOR 加密写出。
头部 CRC 随便填（因为读档时我们用补丁 so 跳过 CRC 校验；之后让游戏自己重存写正确 CRC）。
用法:
  python edit_save.py --save rs/0002 --global-metadata tools/global-metadata.dat \
      --money 999824740 --res 9999 9999 999 999 --out rs/0002.mod
注意:
  金币字段=游戏内金币/10，且为 int32 (上限约 21.4 亿；显示上限约 9.99 亿 G)
  资源为 int16 (上限 65535)；但显示格最多4位，后两项游戏会夹到 999
"""
import argparse, struct

KS = bytes.fromhex(
    "65b648ad7a082f13fdaa4be9c6fb7142b7491e48f1d73908aa32baca1b27f2b5b4c0adb69e7a5d2518906564"
)
MONEY_OFF = 1912
RES_OFFS = [15510, 15512, 15514, 15516]
RES_CAP = {15510: 9999, 15512: 9999, 15514: 999, 15516: 999}


def load_ks(gm_path, offset=0x30DA18):
    if not gm_path:
        return KS
    with open(gm_path, "rb") as f:
        d = f.read()
    return d[offset: offset + 44]


def decrypt(enc, ks):
    return bytearray(enc[i] ^ ks[i % 44] for i in range(len(enc)))


def encrypt(plain, ks):
    return bytes(plain[i] ^ ks[i % 44] for i in range(len(plain)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", required=True)
    ap.add_argument("--global-metadata")
    ap.add_argument("--money", type=int, required=True, help="游戏内金币数(会÷10存入)")
    ap.add_argument("--res", nargs=4, type=int, required=True, metavar=("R1", "R2", "R3", "R4"),
                    help="四个资源目标值(心/灯泡/奖杯/第4项)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ks = load_ks(args.global_metadata)
    raw = open(args.save, "rb").read()
    plain = decrypt(raw, ks)

    if plain[0:4] != b"\x00\x00\x00\x00":
        raise SystemExit("[!] 解密自检失败：前4字节非0，密钥流或文件可能不对")

    # 金币
    field = args.money // 10
    if not (0 <= field <= 0x7FFFFFFF):
        raise SystemExit(f"[!] 金币字段溢出 int32: {field}")
    plain[MONEY_OFF:MONEY_OFF + 4] = struct.pack(">I", field)

    # 资源
    warn = []
    for off, val in zip(RES_OFFS, args.res):
        if not (0 <= val <= 0xFFFF):
            raise SystemExit(f"[!] 资源 @ {off} 超出 int16: {val}")
        plain[off:off + 2] = struct.pack(">H", val)
        if val > RES_CAP[off]:
            warn.append((off, val, RES_CAP[off]))

    out = encrypt(plain, ks)
    open(args.out, "wb").write(out)
    print(f"已写出: {args.out}  (长度 {len(out)})")
    print(f"金币字段 = {field}  -> 游戏内 {field*10:,} G")
    print(f"资源 = {args.res}")
    if warn:
        print("[!] 警告: 以下资源超过显示/钳制上限，可能显示白块或被夹到上限:")
        for off, val, cap in warn:
            print(f"    offset {off}: 你填 {val} > 上限 {cap}")


if __name__ == "__main__":
    main()
