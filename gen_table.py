#!/usr/bin/env python3
import urllib.request
import re
import sys

TBL_URL_64 = "https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/entry/syscalls/syscall_64.tbl"
TBL_URL_32 = "https://raw.githubusercontent.com/torvalds/linux/master/arch/x86/entry/syscalls/syscall_32.tbl"

HDR_URL = "https://raw.githubusercontent.com/torvalds/linux/master/include/linux/syscalls.h"

T_INT  = "INT"
T_STR  = "STR"
T_PTR  = "PTR"
T_VOID = "0"

def get_c_type(arg_string):
    arg = arg_string.lower()
    if "char" in arg and "*" in arg:
        return T_STR
    if "*" in arg or "struct" in arg:
        return T_PTR
    return T_INT

def parse_header_types():
    """Parses include/linux/syscalls.h to get function prototypes."""
    print(f"Fetching {HDR_URL}...", file=sys.stderr)
    try:
        with urllib.request.urlopen(HDR_URL) as response:
            header_data = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching header: {e}", file=sys.stderr)
        sys.exit(1)

    types_map = {}
    pattern = re.compile(r'asmlinkage\s+long\s+sys_([a-zA-Z0-9_]+)\s*\(([^)]*)\)')
    
    matches = pattern.finditer(header_data)
    for match in matches:
        name = match.group(1)
        args_str = match.group(2)

        if args_str.strip() == "void":
            types_map[name] = []
            continue

        args_list = [arg.strip() for arg in args_str.split(',')]
        mapped_args = [get_c_type(arg) for arg in args_list]
        types_map[name] = mapped_args

    return types_map

def parse_syscall_table(mode):
    """Parses the ABI table based on mode (32 or 64)."""
    url = TBL_URL_32 if mode == "32" else TBL_URL_64
    valid_abis = ['i386'] if mode == "32" else ['common', '64']
    
    print(f"Fetching {url}...", file=sys.stderr)
    try:
        with urllib.request.urlopen(url) as response:
            tbl_data = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching table: {e}", file=sys.stderr)
        sys.exit(1)

    syscalls = {}
    max_id = 0

    for line in tbl_data.splitlines():
        line = line.split('#')[0].strip()
        if not line: continue
        parts = line.split()
        
        # <number> <abi> <name> <entry point>
        if len(parts) >= 3 and parts[1] in valid_abis:
            try:
                nr = int(parts[0])
                name = parts[2]
                syscalls[nr] = name
                if nr > max_id: max_id = nr
            except ValueError:
                continue
    return syscalls, max_id

def generate(tbl_data, type_data, max_id, mode):
    arch_name = "I386" if mode == "32" else "X86_64"
    
    out = []
    out.append(f"#ifndef SYSCALL{mode}_H")
    out.append(f"# define SYSCALL{mode}_H")
    out.append("")
    out.append(f"# define MAX_{arch_name}_SYSCALL {max_id + 1}")
    out.append("")
    out.append(f"# define {arch_name}_SYSCALL {{ \\")

    for i in range(max_id + 1):
        if i in tbl_data:
            name = tbl_data[i]
            
            args = type_data.get(name, [T_INT]*6)
            argc = len(type_data.get(name, [0]*6))

            padded = list(args)
            while len(padded) < 6:
                padded.append(T_VOID)
            padded = padded[:6]
            
            arg_str = ", ".join(padded)
            out.append(f'[{i:3}] = {{"{name}", {argc}, {{{arg_str}}}, INT}}, \\')
        else:
            out.append(f'[{i:3}] = {{"unknown", 0, {{0, 0, 0, 0, 0, 0}}, INT}}, \\')

    out[-1] = out[-1].rstrip(" \\") + " \\"
    out.append("}")
    out.append("")
    out.append("#endif")
    return "\n".join(out)

if __name__ == "__main__":
    mode = "64"
    if len(sys.argv) > 1 and sys.argv[1] == "32":
        mode = "32"
    
    print(f"Generating table for: {mode}-bit", file=sys.stderr)

    print("Step 1: Parsing Kernel Header for Types...", file=sys.stderr)
    types_map = parse_header_types()
    print("Step 2: Parsing ABI Table for IDs...", file=sys.stderr)
    syscalls, max_id = parse_syscall_table(mode)

    # 4. Output
    print(generate(syscalls, types_map, max_id, mode))