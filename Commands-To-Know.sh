#!/bin/sh

 #Copy all the firmware files simultaneously
for i in 0 1 2 3 4 5 6 7 8 9 10 11 12 13; do dd if=/dev/mtd$i of=mtd$i.bin bs=1M; done
