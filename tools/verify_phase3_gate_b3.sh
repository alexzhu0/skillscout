#!/bin/sh
set -eu

fail() {
    printf '%s\n' 'phase3 Gate B3 preflight failed' >&2
    exit 1
}

[ "$#" -eq 0 ] || fail

test_seam=${SKILLSCOUT_PHASE3_GATE_B3_TEST_SEAM-}
case "$test_seam" in
    ""|lock_after_lstat|lock_after_read) ;;
    *) fail ;;
esac

case "$0" in
    */*) script_parent=${0%/*} ;;
    *) script_parent=. ;;
esac
script_directory=$(CDPATH= cd -P "$script_parent" 2>/dev/null && pwd -P) || fail
repository_root=$(CDPATH= cd -P "$script_directory/.." 2>/dev/null && pwd -P) || fail

[ -x /usr/bin/perl ] || fail
/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C \
    /usr/bin/perl -MDigest::SHA -MFcntl -MTime::HiRes -e 1 \
    >/dev/null 2>&1 || fail

exec /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C \
    /usr/bin/perl - "$repository_root" "$test_seam" <<'PERL'
use strict;
use warnings;

use Digest::SHA ();
use Fcntl qw(
    FD_CLOEXEC F_GETFD F_SETFD O_RDONLY O_NOFOLLOW S_IFMT S_IFREG
);
use Time::HiRes ();

my $MAX_DIGEST_BYTES = 65;
my $MAX_LOCK_BYTES = 2_000_000;
my $repository_root = $ARGV[0];
my $test_seam = $ARGV[1];

sub fail_closed {
    print STDERR "phase3 Gate B3 preflight failed\n";
    exit 1;
}

sub require_true {
    fail_closed() if !$_[0];
}

sub metadata_equal {
    my ($left, $right, @indices) = @_;
    for my $index (@indices) {
        return 0 if $left->[$index] != $right->[$index];
    }
    return 1;
}

sub require_admissible_regular {
    my ($metadata, $cap) = @_;
    require_true(@{$metadata} == 13);
    require_true(($metadata->[2] & S_IFMT) == S_IFREG);
    require_true($metadata->[3] == 1);
    require_true($metadata->[4] == $>);
    require_true(($metadata->[2] & 0022) == 0);
    require_true($metadata->[7] >= 0 && $metadata->[7] <= $cap);
}

sub stop_at_test_seam {
    my ($name) = @_;
    return if $test_seam ne $name;
    kill "STOP", $$ or fail_closed();
}

sub read_secure {
    my ($path, $cap, $label) = @_;
    my @before = Time::HiRes::lstat($path);
    require_true(@before == 13);
    require_admissible_regular(\@before, $cap);

    stop_at_test_seam("${label}_after_lstat");

    my $no_follow = eval { O_NOFOLLOW() };
    require_true(defined($no_follow) && $no_follow != 0);
    sysopen(my $stream, $path, O_RDONLY | $no_follow) or fail_closed();

    my $descriptor_flags = fcntl($stream, F_GETFD, 0);
    require_true(defined($descriptor_flags));
    require_true(
        defined(fcntl($stream, F_SETFD, $descriptor_flags | FD_CLOEXEC))
    );
    my $closed_on_exec = fcntl($stream, F_GETFD, 0);
    require_true(
        defined($closed_on_exec) && ($closed_on_exec & FD_CLOEXEC) == FD_CLOEXEC
    );

    my @opened = Time::HiRes::stat($stream);
    require_admissible_regular(\@opened, $cap);
    require_true(metadata_equal(\@before, \@opened, 0, 1, 2, 3, 4));

    binmode($stream) or fail_closed();
    my $sha256 = Digest::SHA->new(256);
    my $raw = "";
    my $consumed = 0;
    while (1) {
        my $remaining = $cap + 1 - $consumed;
        last if $remaining <= 0;
        my $length = $remaining < 8192 ? $remaining : 8192;
        my $chunk = "";
        my $read = sysread($stream, $chunk, $length);
        require_true(defined($read));
        last if $read == 0;
        $consumed += $read;
        require_true($consumed <= $cap);
        $raw .= substr($chunk, 0, $read);
        $sha256->add(substr($chunk, 0, $read));
    }

    stop_at_test_seam("${label}_after_read");

    my @after_descriptor = Time::HiRes::stat($stream);
    my @after_path = Time::HiRes::lstat($path);
    require_admissible_regular(\@after_descriptor, $cap);
    require_admissible_regular(\@after_path, $cap);
    require_true(
        metadata_equal(
            \@opened,
            \@after_descriptor,
            0, 1, 2, 3, 4, 7, 9, 10
        )
    );
    require_true(
        metadata_equal(
            \@after_descriptor,
            \@after_path,
            0, 1, 2, 3, 4, 7, 9, 10
        )
    );
    close($stream) or fail_closed();
    return ($raw, $sha256->hexdigest);
}

my $completed = eval {
    my $digest_path =
        $repository_root . "/config/supply-chain/phase3-gate-b3.lock.sha256";
    my $lock_path = $repository_root . "/uv.lock";

    my ($digest_bytes, undef) =
        read_secure($digest_path, $MAX_DIGEST_BYTES, "digest");
    require_true($digest_bytes =~ /\A([0-9a-f]{64})\n\z/);
    my $approved_digest = $1;

    my (undef, $lock_digest) =
        read_secure($lock_path, $MAX_LOCK_BYTES, "lock");
    require_true($lock_digest eq $approved_digest);
    return 1;
};
fail_closed() if !$completed;
exit 0;
PERL
