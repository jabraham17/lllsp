; ModuleID = '/app/example.c'
source_filename = "/app/example.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @bar(i32 noundef %i) #0 !dbg !10 {
entry:
  %i.addr = alloca i32, align 4
  store i32 %i, ptr %i.addr, align 4
    #dbg_declare(ptr %i.addr, !16, !DIExpression(), !17)
  %0 = load i32, ptr %i.addr, align 4, !dbg !18
  %add = add nsw i32 %0, 1, !dbg !19
  ret i32 %add, !dbg !20
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @foo(i32 noundef %i) #0 !dbg !21 {
entry:
  %i.addr = alloca i32, align 4
  store i32 %i, ptr %i.addr, align 4
    #dbg_declare(ptr %i.addr, !22, !DIExpression(), !23)
  %0 = load i32, ptr %i.addr, align 4, !dbg !24
  %call = call i32 @bar(i32 noundef %0), !dbg !25
  %add = add nsw i32 %call, 1, !dbg !26
  ret i32 %add, !dbg !27
}

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cmov,+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!2, !3, !4, !5, !6, !7, !8}
!llvm.ident = !{!9}

!0 = distinct !DICompileUnit(language: DW_LANG_C11, file: !1, producer: "clang version 20.0.0git (https://github.com/llvm/llvm-project.git a5af6214dd0e9d53c66dc06bcd23540b05c70120)", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, splitDebugInlining: false, nameTableKind: None)
!1 = !DIFile(filename: "/app/example.c", directory: "/app")
!2 = !{i32 7, !"Dwarf Version", i32 4}
!3 = !{i32 2, !"Debug Info Version", i32 3}
!4 = !{i32 1, !"wchar_size", i32 4}
!5 = !{i32 8, !"PIC Level", i32 2}
!6 = !{i32 7, !"PIE Level", i32 2}
!7 = !{i32 7, !"uwtable", i32 2}
!8 = !{i32 7, !"frame-pointer", i32 2}
!9 = !{!"clang version 20.0.0git (https://github.com/llvm/llvm-project.git a5af6214dd0e9d53c66dc06bcd23540b05c70120)"}
!10 = distinct !DISubprogram(name: "bar", scope: !11, file: !11, line: 1, type: !12, scopeLine: 1, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !15)
!11 = !DIFile(filename: "example.c", directory: "/app")
!12 = !DISubroutineType(types: !13)
!13 = !{!14, !14}
!14 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!15 = !{}
!16 = !DILocalVariable(name: "i", arg: 1, scope: !10, file: !11, line: 1, type: !14)
!17 = !DILocation(line: 1, column: 13, scope: !10)
!18 = !DILocation(line: 1, column: 24, scope: !10)
!19 = !DILocation(line: 1, column: 25, scope: !10)
!20 = !DILocation(line: 1, column: 17, scope: !10)
!21 = distinct !DISubprogram(name: "foo", scope: !11, file: !11, line: 3, type: !12, scopeLine: 3, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !15)
!22 = !DILocalVariable(name: "i", arg: 1, scope: !21, file: !11, line: 3, type: !14)
!23 = !DILocation(line: 3, column: 13, scope: !21)
!24 = !DILocation(line: 4, column: 16, scope: !21)
!25 = !DILocation(line: 4, column: 12, scope: !21)
!26 = !DILocation(line: 4, column: 18, scope: !21)
!27 = !DILocation(line: 4, column: 5, scope: !21)
