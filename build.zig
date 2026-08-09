const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    // Plain standardOptimizeOption so `-Doptimize=ReleaseFast` stays available;
    // setting preferred_optimize_mode would replace it with `-Drelease`.
    const optimize = b.standardOptimizeOption(.{});

    // The library under test, consumed straight out of vendor/ so there is no
    // doubt about which sources were benchmarked.
    const zstm = b.createModule(.{
        .root_source_file = b.path("vendor/zstm/src/root.zig"),
        .target = target,
        .optimize = optimize,
    });

    const exe = b.addExecutable(.{
        .name = "zstm-bench",
        .root_module = b.createModule(.{
            .root_source_file = b.path("zig/src/main.zig"),
            .target = target,
            .optimize = optimize,
            .imports = &.{.{ .name = "zstm", .module = zstm }},
        }),
    });
    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    if (b.args) |args| run_cmd.addArgs(args);
    b.step("run", "Run the benchmark driver").dependOn(&run_cmd.step);

    // zstm's own test suite, so we can confirm the vendored library is sound on
    // this toolchain before trusting any timing it produces.
    const zstm_tests = b.addTest(.{ .root_module = zstm });
    b.step("test", "Run zstm's test suite").dependOn(&b.addRunArtifact(zstm_tests).step);
}
