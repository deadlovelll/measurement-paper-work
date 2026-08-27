
/home/timofei/Downloads/Telegram Desktop/measurement-paper-work/measurement-paper-work/bench/build/native/libkernels_c_O3native.so:	file format elf64-x86-64

Disassembly of section .text:

00000000000016b0 <c_matmul>:
    16b0:      	pushq	%rbp
    16b1:      	pushq	%r15
    16b3:      	pushq	%r14
    16b5:      	pushq	%r13
    16b7:      	pushq	%r12
    16b9:      	pushq	%rbx
    16ba:      	movq	%rdx, -0x8(%rsp)
    16bf:      	testq	%rcx, %rcx
    16c2:      	jle	0x183d <c_matmul+0x18d>
    16c8:      	movl	%ecx, %eax
    16ca:      	andl	$0x7, %eax
    16cd:      	movabsq	$0x7ffffffffffffff8, %r8 # imm = 0x7FFFFFFFFFFFFFF8
    16d7:      	andq	%rcx, %r8
    16da:      	leaq	0x38(%rdi), %r9
    16de:      	leaq	(,%rcx,8), %r10
    16e6:      	movq	%rcx, %r11
    16e9:      	shlq	$0x6, %r11
    16ed:      	xorl	%edx, %edx
    16ef:      	jmp	0x1712 <c_matmul+0x62>
    16f1:      	nopw	%cs:(%rax,%rax)
    1700:      	incq	%rdx
    1703:      	addq	%r10, %r9
    1706:      	addq	%r10, %rdi
    1709:      	cmpq	%rcx, %rdx
    170c:      	je	0x183d <c_matmul+0x18d>
    1712:      	movq	%rdx, %rbx
    1715:      	imulq	%rcx, %rbx
    1719:      	movq	-0x8(%rsp), %r14
    171e:      	leaq	(%r14,%rbx,8), %r14
    1722:      	movq	%rsi, %r15
    1725:      	xorl	%r12d, %r12d
    1728:      	jmp	0x1742 <c_matmul+0x92>
    172a:      	nopw	(%rax,%rax)
    1730:      	vmovsd	%xmm0, (%r14,%r12,8)
    1736:      	incq	%r12
    1739:      	addq	$0x8, %r15
    173d:      	cmpq	%rcx, %r12
    1740:      	je	0x1700 <c_matmul+0x50>
    1742:      	vxorpd	%xmm0, %xmm0, %xmm0
    1746:      	cmpq	$0x8, %rcx
    174a:      	jae	0x1760 <c_matmul+0xb0>
    174c:      	xorl	%r13d, %r13d
    174f:      	jmp	0x17fb <c_matmul+0x14b>
    1754:      	nopw	%cs:(%rax,%rax)
    1760:      	movq	%r15, %rbp
    1763:      	xorl	%r13d, %r13d
    1766:      	nopw	%cs:(%rax,%rax)
    1770:      	vmovsd	-0x38(%r9,%r13,8), %xmm1
    1777:      	vmovsd	-0x30(%r9,%r13,8), %xmm2
    177e:      	vfmadd132sd	(%rbp), %xmm0, %xmm1 # xmm1 = (xmm1 * mem) + xmm0
    1784:      	leaq	(%r10,%rbp), %rbx
    1788:      	vfmadd231sd	(%rbp,%r10), %xmm2, %xmm1 # xmm1 = (xmm2 * mem) + xmm1
    178f:      	vmovsd	-0x28(%r9,%r13,8), %xmm0
    1796:      	vfmadd132sd	(%r10,%rbx), %xmm1, %xmm0 # xmm0 = (xmm0 * mem) + xmm1
    179c:      	addq	%r10, %rbx
    179f:      	vmovsd	-0x20(%r9,%r13,8), %xmm1
    17a6:      	vfmadd132sd	(%r10,%rbx), %xmm0, %xmm1 # xmm1 = (xmm1 * mem) + xmm0
    17ac:      	addq	%r10, %rbx
    17af:      	vmovsd	-0x18(%r9,%r13,8), %xmm0
    17b6:      	vfmadd132sd	(%r10,%rbx), %xmm1, %xmm0 # xmm0 = (xmm0 * mem) + xmm1
    17bc:      	addq	%r10, %rbx
    17bf:      	vmovsd	-0x10(%r9,%r13,8), %xmm1
    17c6:      	vfmadd132sd	(%r10,%rbx), %xmm0, %xmm1 # xmm1 = (xmm1 * mem) + xmm0
    17cc:      	addq	%r10, %rbx
    17cf:      	vmovsd	-0x8(%r9,%r13,8), %xmm2
    17d6:      	vfmadd132sd	(%r10,%rbx), %xmm1, %xmm2 # xmm2 = (xmm2 * mem) + xmm1
    17dc:      	addq	%r10, %rbx
    17df:      	vmovsd	(%r9,%r13,8), %xmm0
    17e5:      	vfmadd132sd	(%r10,%rbx), %xmm2, %xmm0 # xmm0 = (xmm0 * mem) + xmm2
    17eb:      	addq	$0x8, %r13
    17ef:      	addq	%r11, %rbp
    17f2:      	cmpq	%r13, %r8
    17f5:      	jne	0x1770 <c_matmul+0xc0>
    17fb:      	testq	%rax, %rax
    17fe:      	je	0x1730 <c_matmul+0x80>
    1804:      	movq	%r10, %rbp
    1807:      	imulq	%r13, %rbp
    180b:      	addq	%r15, %rbp
    180e:      	leaq	(%rdi,%r13,8), %r13
    1812:      	xorl	%ebx, %ebx
    1814:      	nopw	%cs:(%rax,%rax)
    1820:      	vmovsd	(%r13,%rbx,8), %xmm1
    1827:      	vfmadd231sd	(%rbp), %xmm1, %xmm0 # xmm0 = (xmm1 * mem) + xmm0
    182d:      	incq	%rbx
    1830:      	addq	%r10, %rbp
    1833:      	cmpq	%rbx, %rax
    1836:      	jne	0x1820 <c_matmul+0x170>
    1838:      	jmp	0x1730 <c_matmul+0x80>
    183d:      	popq	%rbx
    183e:      	popq	%r12
    1840:      	popq	%r13
    1842:      	popq	%r14
    1844:      	popq	%r15
    1846:      	popq	%rbp
    1847:      	retq
    1848:      	nopl	(%rax,%rax)
