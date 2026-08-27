
/home/timofei/Downloads/Telegram Desktop/measurement-paper-work/measurement-paper-work/bench/build/native/libbranchy_c.so:	file format elf64-x86-64

Disassembly of section .text:

0000000000001130 <c_tokenize>:
    1130:      	xorl	%r11d, %r11d
    1133:      	testq	%rsi, %rsi
    1136:      	jle	0x1153 <c_tokenize+0x23>
    1138:      	cmpq	$0x1, %rsi
    113c:      	jne	0x115b <c_tokenize+0x2b>
    113e:      	xorl	%eax, %eax
    1140:      	xorl	%r8d, %r8d
    1143:      	xorl	%ecx, %ecx
    1145:      	testb	$0x1, %sil
    1149:      	jne	0x131a <c_tokenize+0x1ea>
    114f:      	movq	%rcx, (%rdx)
    1152:      	retq
    1153:      	xorl	%ecx, %ecx
    1155:      	xorl	%eax, %eax
    1157:      	movq	%rcx, (%rdx)
    115a:      	retq
    115b:      	pushq	%rbp
    115c:      	pushq	%r15
    115e:      	pushq	%r14
    1160:      	pushq	%r12
    1162:      	pushq	%rbx
    1163:      	movabsq	$0x7ffffffffffffffe, %r9 # imm = 0x7FFFFFFFFFFFFFFE
    116d:      	andq	%rsi, %r9
    1170:      	xorl	%eax, %eax
    1172:      	movabsq	$0x100000600, %r10      # imm = 0x100000600
    117c:      	xorl	%r8d, %r8d
    117f:      	xorl	%r11d, %r11d
    1182:      	xorl	%ecx, %ecx
    1184:      	jmp	0x11b1 <c_tokenize+0x81>
    1186:      	nopw	%cs:(%rax,%rax)
    1190:      	cmpb	$-0xa, %bl
    1193:      	adcq	$0x0, %rax
    1197:      	addl	$-0x30, %r12d
    119b:      	addq	%r12, %rcx
    119e:      	movl	$0x1, %r11d
    11a4:      	addq	$0x2, %r8
    11a8:      	cmpq	%r8, %r9
    11ab:      	je	0x1308 <c_tokenize+0x1d8>
    11b1:      	movzbl	(%rdi,%r8), %r15d
    11b6:      	leal	-0x3a(%r15), %ebx
    11ba:      	cmpb	$-0xa, %bl
    11bd:      	jae	0x1210 <c_tokenize+0xe0>
    11bf:      	movl	%r15d, %ebp
    11c2:      	andb	$-0x21, %bpl
    11c6:      	addb	$-0x41, %bpl
    11ca:      	cmpb	$0x19, %bpl
    11ce:      	ja	0x1250 <c_tokenize+0x120>
    11d4:      	xorl	%r14d, %r14d
    11d7:      	cmpl	$0x2, %r11d
    11db:      	setne	%r14b
    11df:      	addq	%r14, %rax
    11e2:      	orq	$0x20, %r15
    11e6:      	addq	%r15, %rcx
    11e9:      	addq	$-0x60, %rcx
    11ed:      	movl	$0x1, %r15d
    11f3:      	xorl	%r14d, %r14d
    11f6:      	movzbl	0x1(%rdi,%r8), %r12d
    11fc:      	leal	-0x30(%r12), %r11d
    1201:      	cmpb	$0xa, %r11b
    1205:      	jb	0x1190 <c_tokenize+0x60>
    1207:      	jmp	0x12b0 <c_tokenize+0x180>
    120c:      	nopl	(%rax)
    1210:      	xorl	%r14d, %r14d
    1213:      	cmpl	$0x1, %r11d
    1217:      	setne	%r14b
    121b:      	addq	%r14, %rax
    121e:      	addl	$-0x30, %r15d
    1222:      	addq	%r15, %rcx
    1225:      	movl	$0x1, %r15d
    122b:      	movl	$0x1, %r14d
    1231:      	movzbl	0x1(%rdi,%r8), %r12d
    1237:      	leal	-0x30(%r12), %r11d
    123c:      	cmpb	$0xa, %r11b
    1240:      	jb	0x1190 <c_tokenize+0x60>
    1246:      	jmp	0x12b0 <c_tokenize+0x180>
    1248:      	nopl	(%rax,%rax)
    1250:      	movl	$0x1, %r14d
    1256:      	cmpb	$0x20, %r15b
    125a:      	ja	0x127f <c_tokenize+0x14f>
    125c:      	btq	%r15, %r10
    1260:      	jae	0x127f <c_tokenize+0x14f>
    1262:      	movl	$0x1, %r15d
    1268:      	movzbl	0x1(%rdi,%r8), %r12d
    126e:      	leal	-0x30(%r12), %r11d
    1273:      	cmpb	$0xa, %r11b
    1277:      	jb	0x1190 <c_tokenize+0x60>
    127d:      	jmp	0x12b0 <c_tokenize+0x180>
    127f:      	xorl	%r15d, %r15d
    1282:      	cmpl	$0x3, %r11d
    1286:      	setne	%r15b
    128a:      	addq	%r15, %rax
    128d:      	addq	$0x7, %rcx
    1291:      	xorl	%r15d, %r15d
    1294:      	movzbl	0x1(%rdi,%r8), %r12d
    129a:      	leal	-0x30(%r12), %r11d
    129f:      	cmpb	$0xa, %r11b
    12a3:      	jb	0x1190 <c_tokenize+0x60>
    12a9:      	nopl	(%rax)
    12b0:      	movl	%r12d, %r11d
    12b3:      	andb	$-0x21, %r11b
    12b7:      	addb	$-0x41, %r11b
    12bb:      	cmpb	$0x1a, %r11b
    12bf:      	jae	0x12e0 <c_tokenize+0x1b0>
    12c1:      	addq	%r14, %rax
    12c4:      	orq	$0x20, %r12
    12c8:      	addq	%r12, %rcx
    12cb:      	addq	$-0x60, %rcx
    12cf:      	movl	$0x2, %r11d
    12d5:      	jmp	0x11a4 <c_tokenize+0x74>
    12da:      	nopw	(%rax,%rax)
    12e0:      	cmpl	$0x20, %r12d
    12e4:      	ja	0x12f6 <c_tokenize+0x1c6>
    12e6:      	xorl	%r11d, %r11d
    12e9:      	movl	%r12d, %ebx
    12ec:      	btq	%rbx, %r10
    12f0:      	jb	0x11a4 <c_tokenize+0x74>
    12f6:      	addq	%r15, %rax
    12f9:      	addq	$0x7, %rcx
    12fd:      	movl	$0x3, %r11d
    1303:      	jmp	0x11a4 <c_tokenize+0x74>
    1308:      	popq	%rbx
    1309:      	popq	%r12
    130b:      	popq	%r14
    130d:      	popq	%r15
    130f:      	popq	%rbp
    1310:      	testb	$0x1, %sil
    1314:      	je	0x114f <c_tokenize+0x1f>
    131a:      	movzbl	(%rdi,%r8), %esi
    131f:      	leal	-0x30(%rsi), %edi
    1322:      	cmpb	$0xa, %dil
    1326:      	jae	0x133f <c_tokenize+0x20f>
    1328:      	xorl	%edi, %edi
    132a:      	cmpl	$0x1, %r11d
    132e:      	setne	%dil
    1332:      	addq	%rdi, %rax
    1335:      	addl	$-0x30, %esi
    1338:      	addq	%rsi, %rcx
    133b:      	movq	%rcx, (%rdx)
    133e:      	retq
    133f:      	movl	%esi, %edi
    1341:      	andb	$-0x21, %dil
    1345:      	addb	$-0x41, %dil
    1349:      	cmpb	$0x1a, %dil
    134d:      	jae	0x136b <c_tokenize+0x23b>
    134f:      	xorl	%edi, %edi
    1351:      	cmpl	$0x2, %r11d
    1355:      	setne	%dil
    1359:      	addq	%rdi, %rax
    135c:      	orq	$0x20, %rsi
    1360:      	addq	%rsi, %rcx
    1363:      	addq	$-0x60, %rcx
    1367:      	movq	%rcx, (%rdx)
    136a:      	retq
    136b:      	cmpl	$0x20, %esi
    136e:      	ja	0x1386 <c_tokenize+0x256>
    1370:      	movl	%esi, %esi
    1372:      	movabsq	$0x100000600, %rdi      # imm = 0x100000600
    137c:      	btq	%rsi, %rdi
    1380:      	jb	0x114f <c_tokenize+0x1f>
    1386:      	xorl	%esi, %esi
    1388:      	cmpl	$0x3, %r11d
    138c:      	setne	%sil
    1390:      	addq	%rsi, %rax
    1393:      	addq	$0x7, %rcx
    1397:      	movq	%rcx, (%rdx)
    139a:      	retq
    139b:      	nopl	(%rax,%rax)
