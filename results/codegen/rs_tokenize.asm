
/home/timofei/Downloads/Telegram Desktop/measurement-paper-work/measurement-paper-work/bench/build/native/libmpkernels.so:	file format elf64-x86-64

Disassembly of section .text:

000000000000d830 <rs_tokenize>:
    d830:      	testq	%rsi, %rsi
    d833:      	je	0xd86c <rs_tokenize+0x3c>
    d835:      	pushq	%rbp
    d836:      	pushq	%r14
    d838:      	pushq	%rbx
    d839:      	cmpq	$0x1, %rsi
    d83d:      	jne	0xd874 <rs_tokenize+0x44>
    d83f:      	xorl	%r11d, %r11d
    d842:      	xorl	%ecx, %ecx
    d844:      	xorl	%eax, %eax
    d846:      	movzbl	(%rdi), %esi
    d849:      	leal	-0x30(%rsi), %edi
    d84c:      	cmpb	$0xa, %dil
    d850:      	jae	0xda23 <rs_tokenize+0x1f3>
    d856:      	xorl	%esi, %esi
    d858:      	cmpb	$0x1, %r11b
    d85c:      	setne	%sil
    d860:      	addq	%rsi, %rax
    d863:      	movzbl	%dil, %esi
    d867:      	jmp	0xda4c <rs_tokenize+0x21c>
    d86c:      	xorl	%ecx, %ecx
    d86e:      	xorl	%eax, %eax
    d870:      	movq	%rcx, (%rdx)
    d873:      	retq
    d874:      	movq	%rsi, %r8
    d877:      	andq	$-0x2, %r8
    d87b:      	xorl	%eax, %eax
    d87d:      	movabsq	$0x100000600, %r10      # imm = 0x100000600
    d887:      	xorl	%ecx, %ecx
    d889:      	xorl	%r11d, %r11d
    d88c:      	jmp	0xd8b0 <rs_tokenize+0x80>
    d88e:      	nop
    d890:      	cmpb	$0xa, %dil
    d894:      	sbbq	$-0x1, %rax
    d898:      	movzbl	%bpl, %edi
    d89c:      	addq	%rdi, %rcx
    d89f:      	movb	$0x1, %r11b
    d8a2:      	leaq	0x2(%r9), %rdi
    d8a6:      	addq	$-0x2, %r8
    d8aa:      	je	0xda06 <rs_tokenize+0x1d6>
    d8b0:      	movq	%rdi, %r9
    d8b3:      	movzbl	(%rdi), %r14d
    d8b7:      	leal	-0x30(%r14), %edi
    d8bb:      	cmpb	$0x9, %dil
    d8bf:      	jbe	0xd910 <rs_tokenize+0xe0>
    d8c1:      	movl	%r14d, %ebx
    d8c4:      	andb	$-0x21, %bl
    d8c7:      	addb	$-0x41, %bl
    d8ca:      	cmpb	$0x1a, %bl
    d8cd:      	jae	0xd950 <rs_tokenize+0x120>
    d8d3:      	xorl	%ebx, %ebx
    d8d5:      	cmpb	$0x2, %r11b
    d8d9:      	setne	%bl
    d8dc:      	addq	%rbx, %rax
    d8df:      	orb	$0x20, %r14b
    d8e3:      	addb	$-0x60, %r14b
    d8e7:      	movzbl	%r14b, %r11d
    d8eb:      	addq	%r11, %rcx
    d8ee:      	movl	$0x1, %r11d
    d8f4:      	xorl	%ebx, %ebx
    d8f6:      	movzbl	0x1(%r9), %r14d
    d8fb:      	leal	-0x30(%r14), %ebp
    d8ff:      	cmpb	$0xa, %bpl
    d903:      	jb	0xd890 <rs_tokenize+0x60>
    d905:      	jmp	0xd9b0 <rs_tokenize+0x180>
    d90a:      	nopw	(%rax,%rax)
    d910:      	xorl	%ebx, %ebx
    d912:      	cmpb	$0x1, %r11b
    d916:      	setne	%bl
    d919:      	addq	%rbx, %rax
    d91c:      	movzbl	%dil, %r11d
    d920:      	addq	%r11, %rcx
    d923:      	movl	$0x1, %r11d
    d929:      	movl	$0x1, %ebx
    d92e:      	movzbl	0x1(%r9), %r14d
    d933:      	leal	-0x30(%r14), %ebp
    d937:      	cmpb	$0xa, %bpl
    d93b:      	jb	0xd890 <rs_tokenize+0x60>
    d941:      	jmp	0xd9b0 <rs_tokenize+0x180>
    d943:      	nopw	%cs:(%rax,%rax)
    d950:      	movl	$0x1, %ebx
    d955:      	cmpl	$0x20, %r14d
    d959:      	ja	0xd97f <rs_tokenize+0x14f>
    d95b:      	movl	%r14d, %r14d
    d95e:      	btq	%r14, %r10
    d962:      	jae	0xd97f <rs_tokenize+0x14f>
    d964:      	movl	$0x1, %r11d
    d96a:      	movzbl	0x1(%r9), %r14d
    d96f:      	leal	-0x30(%r14), %ebp
    d973:      	cmpb	$0xa, %bpl
    d977:      	jb	0xd890 <rs_tokenize+0x60>
    d97d:      	jmp	0xd9b0 <rs_tokenize+0x180>
    d97f:      	xorl	%r14d, %r14d
    d982:      	cmpb	$0x3, %r11b
    d986:      	setne	%r14b
    d98a:      	addq	%r14, %rax
    d98d:      	addq	$0x7, %rcx
    d991:      	xorl	%r11d, %r11d
    d994:      	movzbl	0x1(%r9), %r14d
    d999:      	leal	-0x30(%r14), %ebp
    d99d:      	cmpb	$0xa, %bpl
    d9a1:      	jb	0xd890 <rs_tokenize+0x60>
    d9a7:      	nopw	(%rax,%rax)
    d9b0:      	movl	%r14d, %edi
    d9b3:      	andb	$-0x21, %dil
    d9b7:      	addb	$-0x41, %dil
    d9bb:      	cmpb	$0x1a, %dil
    d9bf:      	jae	0xd9e0 <rs_tokenize+0x1b0>
    d9c1:      	addq	%rbx, %rax
    d9c4:      	orb	$0x20, %r14b
    d9c8:      	addb	$-0x60, %r14b
    d9cc:      	movzbl	%r14b, %edi
    d9d0:      	addq	%rdi, %rcx
    d9d3:      	movb	$0x2, %r11b
    d9d6:      	jmp	0xd8a2 <rs_tokenize+0x72>
    d9db:      	nopl	(%rax,%rax)
    d9e0:      	cmpl	$0x20, %r14d
    d9e4:      	ja	0xd9f7 <rs_tokenize+0x1c7>
    d9e6:      	movl	%r14d, %edi
    d9e9:      	btq	%rdi, %r10
    d9ed:      	jae	0xd9f7 <rs_tokenize+0x1c7>
    d9ef:      	xorl	%r11d, %r11d
    d9f2:      	jmp	0xd8a2 <rs_tokenize+0x72>
    d9f7:      	addq	%r11, %rax
    d9fa:      	addq	$0x7, %rcx
    d9fe:      	movb	$0x3, %r11b
    da01:      	jmp	0xd8a2 <rs_tokenize+0x72>
    da06:      	testb	$0x1, %sil
    da0a:      	je	0xda4f <rs_tokenize+0x21f>
    da0c:      	addq	$0x2, %r9
    da10:      	movq	%r9, %rdi
    da13:      	movzbl	(%rdi), %esi
    da16:      	leal	-0x30(%rsi), %edi
    da19:      	cmpb	$0xa, %dil
    da1d:      	jb	0xd856 <rs_tokenize+0x26>
    da23:      	movl	%esi, %edi
    da25:      	andb	$-0x21, %dil
    da29:      	addb	$-0x41, %dil
    da2d:      	cmpb	$0x1a, %dil
    da31:      	jae	0xda57 <rs_tokenize+0x227>
    da33:      	xorl	%edi, %edi
    da35:      	cmpb	$0x2, %r11b
    da39:      	setne	%dil
    da3d:      	addq	%rdi, %rax
    da40:      	orb	$0x20, %sil
    da44:      	addb	$-0x60, %sil
    da48:      	movzbl	%sil, %esi
    da4c:      	addq	%rsi, %rcx
    da4f:      	popq	%rbx
    da50:      	popq	%r14
    da52:      	popq	%rbp
    da53:      	movq	%rcx, (%rdx)
    da56:      	retq
    da57:      	cmpl	$0x20, %esi
    da5a:      	ja	0xda6e <rs_tokenize+0x23e>
    da5c:      	movl	%esi, %esi
    da5e:      	movabsq	$0x100000600, %rdi      # imm = 0x100000600
    da68:      	btq	%rsi, %rdi
    da6c:      	jb	0xda4f <rs_tokenize+0x21f>
    da6e:      	xorl	%esi, %esi
    da70:      	cmpb	$0x3, %r11b
    da74:      	setne	%sil
    da78:      	addq	%rsi, %rax
    da7b:      	addq	$0x7, %rcx
    da7f:      	jmp	0xda4f <rs_tokenize+0x21f>
    da81:      	int3
    da82:      	int3
    da83:      	int3
    da84:      	int3
    da85:      	int3
    da86:      	int3
    da87:      	int3
    da88:      	int3
    da89:      	int3
    da8a:      	int3
    da8b:      	int3
    da8c:      	int3
    da8d:      	int3
    da8e:      	int3
    da8f:      	int3
