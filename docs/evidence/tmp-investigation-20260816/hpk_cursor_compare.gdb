set pagination off
set confirm off
set remotetimeout 30
target remote 127.0.0.1:24689
break *0x0014F02C
commands
  silent
  if $r4 == 31 || $r4 == 32
    set $obj = $sp + 8
    set $valid = *(unsigned int*)($obj + 8)
    set $local = *(unsigned int*)($obj + 0xC)
    set $total = *(unsigned int*)($obj + 0x10)
    set $remaining = *(unsigned int*)($obj + 0x18)
    set $absolute = $total - $remaining - $valid + $local
    printf "ENTRY=%u ABS=0x%08x LOCAL=0x%08x VALID=0x%08x TOTAL=0x%08x REMAINING=0x%08x\n", $r4, $absolute, $local, $valid, $total, $remaining
    printf "HEADER_WORDS=0x%08x 0x%08x 0x%08x\n", *(unsigned int*)($sp+0x15C), *(unsigned int*)($sp+0x160), *(unsigned int*)($sp+0x164)
    x/12bx $sp+0x15C
  end
  if $r4 == 31
    set $previous_packed = *(unsigned int*)($sp+0x164)
  end
  if $r4 == 32
    printf "PREVIOUS_PACKED=0x%08x\n", $previous_packed
    detach
    quit
  end
  continue
end
continue
