
/home/timofei/Downloads/Telegram Desktop/measurement-paper-work/measurement-paper-work/bench/build/native/libmpkernels.so:	file format elf64-x86-64

Disassembly of section .text:

000000000000d740 <rs_matmul>:
    d740:      	pushq	%r15
    d742:      	pushq	%r14
    d744:      	pushq	%r13
    d746:      	pushq	%r12
    d748:      	pushq	%rbx
    d749:      	testq	%rcx, %rcx
    d74c:      	je	0xd7da <rs_matmul+0x9a>
    d752:      	movq	%rsi, %rax
    d755:      	movq	%rcx, %rsi
    d758:      	imulq	%rcx, %rsi
    d75c:      	leaq	(,%rcx,8), %r11
    d764:      	xorl	%r8d, %r8d
    d767:      	xorl	%ebx, %ebx
    d769:      	nopl	(%rax)
    d770:      	movq	%rbx, %r14
    d773:      	incq	%rbx
    d776:      	imulq	%rcx, %r14
    d77a:      	xorl	%r9d, %r9d
    d77d:      	nopl	(%rax)
    d780:      	leaq	0x1(%r9), %r15
    d784:      	vxorpd	%xmm0, %xmm0, %xmm0
    d788:      	movq	%r9, %r10
    d78b:      	xorl	%r12d, %r12d
    d78e:      	nop
    d790:      	leaq	(%r8,%r12), %r13
    d794:      	cmpq	%rsi, %r13
    d797:      	jae	0xd7f3 <rs_matmul+0xb3>
    d799:      	cmpq	%rsi, %r10
    d79c:      	jae	0xd7e4 <rs_matmul+0xa4>
    d79e:      	vmovsd	(%rdi,%r12,8), %xmm1
    d7a4:      	incq	%r12
    d7a7:      	vmulsd	(%rax,%r10,8), %xmm1, %xmm1
    d7ad:      	vaddsd	%xmm1, %xmm0, %xmm0
    d7b1:      	addq	%rcx, %r10
    d7b4:      	cmpq	%r12, %rcx
    d7b7:      	jne	0xd790 <rs_matmul+0x50>
    d7b9:      	addq	%r14, %r9
    d7bc:      	cmpq	%rsi, %r9
    d7bf:      	jae	0xd809 <rs_matmul+0xc9>
    d7c1:      	vmovsd	%xmm0, (%rdx,%r9,8)
    d7c7:      	movq	%r15, %r9
    d7ca:      	cmpq	%rcx, %r15
    d7cd:      	jne	0xd780 <rs_matmul+0x40>
    d7cf:      	addq	%rcx, %r8
    d7d2:      	addq	%r11, %rdi
    d7d5:      	cmpq	%rcx, %rbx
    d7d8:      	jne	0xd770 <rs_matmul+0x30>
    d7da:      	popq	%rbx
    d7db:      	popq	%r12
    d7dd:      	popq	%r13
    d7df:      	popq	%r14
    d7e1:      	popq	%r15
    d7e3:      	retq
    d7e4:      	leaq	0x37635(%rip), %rdx     # 0x44e20 <write+0x44e20>
    d7eb:      	movq	%r10, %rdi
    d7ee:      	callq	0xf5a5 <_ZN4core9panicking18panic_bounds_check17h9ae613628793029fE>
    d7f3:      	cmpq	%rsi, %r8
    d7f6:      	cmovbeq	%rsi, %r8
    d7fa:      	leaq	0x37607(%rip), %rdx     # 0x44e08 <write+0x44e08>
    d801:      	movq	%r8, %rdi
    d804:      	callq	0xf5a5 <_ZN4core9panicking18panic_bounds_check17h9ae613628793029fE>
    d809:      	leaq	0x375e0(%rip), %rdx     # 0x44df0 <write+0x44df0>
    d810:      	movq	%r9, %rdi
    d813:      	callq	0xf5a5 <_ZN4core9panicking18panic_bounds_check17h9ae613628793029fE>
    d818:      	int3
    d819:      	int3
    d81a:      	int3
    d81b:      	int3
    d81c:      	int3
    d81d:      	int3
    d81e:      	int3
    d81f:      	int3
