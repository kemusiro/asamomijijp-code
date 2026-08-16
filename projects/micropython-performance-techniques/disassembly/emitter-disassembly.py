import micropython


@micropython.native
def sum_native(n):
    total = 0
    while n:
        total += n
        n -= 1
    return total


@micropython.viper
def sum_viper(n: int) -> int:
    total = 0
    while n:
        total += n
        n -= 1
    return total


@micropython.asm_thumb
def sum_asm(r0):
    mov(r1, 0)
    label(loop)
    add(r1, r1, r0)
    sub(r0, 1)
    bne(loop)
    mov(r0, r1)


@micropython.native
def xor_native(buf, n, mask):
    for index in range(n):
        buf[index] ^= mask


@micropython.viper
def xor_viper(buf, n: int, mask: int):
    data = ptr8(buf)
    for index in range(n):
        data[index] = data[index] ^ mask


@micropython.asm_thumb
def xor_asm(r0, r1, r2):
    label(loop)
    ldrb(r3, [r0, 0])
    eor(r3, r2)
    strb(r3, [r0, 0])
    add(r0, 1)
    sub(r1, 1)
    bne(loop)
