//! Entry point for `zstm-bench`.
//!
//! Accepts the same flags as RSTM's benchmark binaries (bench/bmharness.cpp),
//! with two additions: `-b` selects the workload (RSTM ships one binary per
//! benchmark; we ship one binary for all four) and `--mode` selects zstm's
//! publication-safety mode.

const std = @import("std");
const zstm = @import("zstm");
const harness = @import("harness.zig");
const workloads = @import("workloads.zig");

const usage =
    \\Usage: zstm-bench -b <workload> [flags]
    \\    -b: workload: Counter | ReadNWrite1 | ReadWriteN | Disjoint
    \\    -d: number of seconds to time (default 1)
    \\    -X: execute fixed tx count, not for a duration
    \\    -p: number of threads (default 1)
    \\    -N: nops between transactions (default 0)
    \\    -R: % lookup txns (remainder split ins/rmv)
    \\    -m: range of keys in data set
    \\    -B: name of benchmark
    \\    -S: number of sets to build (default 1)
    \\    -O: operations per transaction (default 1)
    \\    --mode: ala (default) | sla
    \\    -h: print help (this message)
    \\
;

const Workload = enum { Counter, ReadNWrite1, ReadWriteN, Disjoint };

pub fn main(init: std.process.Init) !void {
    const gpa = init.gpa;
    const cfg = &harness.cfg;

    var workload: ?Workload = null;

    var args = std.process.Args.Iterator.init(init.minimal.args);
    _ = args.skip();

    while (args.next()) |arg| {
        // Flags that take a value; RSTM uses getopt, which accepts both
        // "-p 4" and "-p4". We only need the spaced form.
        const takesValue = struct {
            fn get(it: *std.process.Args.Iterator, name: []const u8) []const u8 {
                return it.next() orelse {
                    std.debug.print("missing value for {s}\n", .{name});
                    std.process.exit(1);
                };
            }
        }.get;

        if (std.mem.eql(u8, arg, "-h")) {
            std.debug.print("{s}", .{usage});
            return;
        } else if (std.mem.eql(u8, arg, "-b")) {
            const v = takesValue(&args, "-b");
            workload = std.meta.stringToEnum(Workload, v) orelse {
                std.debug.print("unknown workload: {s}\n{s}", .{ v, usage });
                std.process.exit(1);
            };
        } else if (std.mem.eql(u8, arg, "--mode")) {
            const v = takesValue(&args, "--mode");
            cfg.mode = if (std.mem.eql(u8, v, "sla")) .sla else .ala;
        } else if (std.mem.eql(u8, arg, "-d")) {
            cfg.duration = try std.fmt.parseInt(u32, takesValue(&args, "-d"), 10);
        } else if (std.mem.eql(u8, arg, "-p")) {
            cfg.threads = try std.fmt.parseInt(u32, takesValue(&args, "-p"), 10);
        } else if (std.mem.eql(u8, arg, "-N")) {
            cfg.nops_after_tx = try std.fmt.parseInt(u32, takesValue(&args, "-N"), 10);
        } else if (std.mem.eql(u8, arg, "-X")) {
            cfg.execute = try std.fmt.parseInt(u32, takesValue(&args, "-X"), 10);
        } else if (std.mem.eql(u8, arg, "-B")) {
            cfg.bmname = takesValue(&args, "-B");
        } else if (std.mem.eql(u8, arg, "-m")) {
            cfg.elements = try std.fmt.parseInt(u32, takesValue(&args, "-m"), 10);
        } else if (std.mem.eql(u8, arg, "-S")) {
            cfg.sets = try std.fmt.parseInt(u32, takesValue(&args, "-S"), 10);
        } else if (std.mem.eql(u8, arg, "-O")) {
            cfg.ops = try std.fmt.parseInt(u32, takesValue(&args, "-O"), 10);
        } else if (std.mem.eql(u8, arg, "-R")) {
            const v = try std.fmt.parseInt(u32, takesValue(&args, "-R"), 10);
            cfg.lookpct = v;
            cfg.inspct = (100 - v) / 2 + v;
        } else {
            std.debug.print("unrecognized argument: {s}\n{s}", .{ arg, usage });
            std.process.exit(1);
        }
    }

    if (cfg.threads == 0 or cfg.threads > 256) {
        std.debug.print("thread count must be in 1..256\n", .{});
        std.process.exit(1);
    }

    var stdout_buffer: [1024]u8 = undefined;
    var stdout_writer: std.Io.File.Writer = .init(.stdout(), init.io, &stdout_buffer);
    const out = &stdout_writer.interface;

    switch (workload orelse {
        std.debug.print("no workload selected\n{s}", .{usage});
        std.process.exit(1);
    }) {
        .Counter => try harness.Runner(workloads.Counter).main(gpa, out),
        .ReadNWrite1 => try harness.Runner(workloads.ReadNWrite1).main(gpa, out),
        .ReadWriteN => try harness.Runner(workloads.ReadWriteN).main(gpa, out),
        .Disjoint => try harness.Runner(workloads.Disjoint).main(gpa, out),
    }
}
