# Tests fail in mock, not in local build.
%bcond_with tests

Name:              valkey
Version:           8.0.4
Release:           3%{?dist}
Summary:           A persistent key-value database
# valkey: BSD-3-Clause
# hiredis: BSD-3-Clause
# hdrhistogram, jemalloc, lzf, linenoise: BSD-2-Clause
# lua: MIT
# fpconv: BSL-1.0
License:           BSD-3-Clause AND BSD-2-Clause AND MIT AND BSL-1.0
URL:               https://valkey.io
Source0:           https://github.com/valkey-io/%{name}/archive/%{version}/%{name}-%{version}.tar.gz
Source1:           %{name}.logrotate
Source2:           %{name}-sentinel.service
Source3:           %{name}.service
Source4:           %{name}.sysusers
Source5:           %{name}.tmpfiles
Source8:           macros.%{name}
Source9:           migrate_redis_to_valkey.sh

Patch1:            valkey-cve-2025-27151.patch

BuildRequires:     make
BuildRequires:     gcc
%if %{with tests}
BuildRequires:     procps-ng
BuildRequires:     tcl
%endif
BuildRequires:     pkgconfig(libsystemd)
BuildRequires:     systemd-devel
BuildRequires:     systemd-rpm-macros
BuildRequires:     openssl-devel
Requires:          logrotate
# from deps/hiredis/hiredis.h
Provides:          bundled(hiredis) = 1.0.3
# from deps/jemalloc/VERSION
Provides:          bundled(jemalloc) = 5.3.0
# from deps/lua/src/lua.h
Provides:          bundled(lua-libs) = 5.1.5
# from deps/linenoise/linenoise.h
Provides:          bundled(linenoise) = 1.0
Provides:          bundled(lzf)
# from deps/hdr_histogram/README.md
Provides:          bundled(hdr_histogram) = 0.11.0
# no version
Provides:          bundled(fpconv)

%global valkey_modules_abi 1
%global valkey_modules_dir %{_libdir}/%{name}/modules
Provides:          valkey(modules_abi)%{?_isa} = %{valkey_modules_abi}

ExcludeArch:       %{ix86}

%description
Valkey is an advanced key-value store. It is often referred to as a data
structure server since keys can contain strings, hashes, lists, sets and
sorted sets.

You can run atomic operations on these types, like appending to a string;
incrementing the value in a hash; pushing to a list; computing set
intersection, union and difference; or getting the member with highest
ranking in a sorted set.

In order to achieve its outstanding performance, Valkey works with an
in-memory dataset. Depending on your use case, you can persist it either
by dumping the dataset to disk every once in a while, or by appending
each command to a log.

Valkey also supports trivial-to-setup master-slave replication, with very
fast non-blocking first synchronization, auto-reconnection on net split
and so forth.

Other features include Transactions, Pub/Sub, Lua scripting, Keys with a
limited time-to-live, and configuration settings to make Valkey behave like
a cache.

You can use Valkey from most programming languages also.

%package           devel
Summary:           Development header for Valkey module development
# Header-Only Library (https://fedoraproject.org/wiki/Packaging:Guidelines)
Provides:          %{name}-static = %{version}-%{release}

%description       devel
Header file required for building loadable Valkey modules.


%package           compat-redis
Summary:           Conversion script and compatibility symlinks for Redis
Requires:          valkey = %{version}-%{release}
%if 0%{?fedora} > 40 || 0%{?rhel} > 9
Obsoletes:         redis < 7.4
Provides:          redis = %{version}-%{release}
%else
Conflicts:         redis < 7.4
%endif
BuildArch:         noarch


%description       compat-redis
%summary


%prep
%setup -qn %{name}-%{version}
%patch -P1 -p1

mv deps/lua/COPYRIGHT             COPYRIGHT-lua
mv deps/jemalloc/COPYING          COPYING-jemalloc
mv deps/hiredis/COPYING COPYING-hiredis-BSD-3-Clause
mv deps/hdr_histogram/LICENSE.txt LICENSE-hdrhistogram
mv deps/hdr_histogram/COPYING.txt COPYING-hdrhistogram
mv deps/fpconv/LICENSE.txt        LICENSE-fpconv

# See https://bugzilla.redhat.com/2240293
# See https://src.fedoraproject.org/rpms/jemalloc/blob/rawhide/f/jemalloc.spec#_34
%ifarch %ix86 %arm x86_64 s390x
sed -e 's/--with-lg-quantum/--with-lg-page=12 --with-lg-quantum/' -i deps/Makefile
%endif
%ifarch ppc64 ppc64le aarch64
sed -e 's/--with-lg-quantum/--with-lg-page=16 --with-lg-quantum/' -i deps/Makefile
%endif

# Module API version safety check
api=`sed -n -e 's/#define VALKEYMODULE_APIVER_[0-9][0-9]* //p' src/valkeymodule.h`
if test "$api" != "%{valkey_modules_abi}"; then
   : Error: Upstream API version is now ${api}, expecting %%{valkey_modules_abi}.
   : Update the valkey_modules_abi macro, the rpmmacros file, and rebuild.
   exit 1
fi


sed -i -e 's|^logfile .*$|logfile /var/log/valkey/valkey.log|g' \
  -e 's|^# unixsocket .*$|unixsocket /run/valkey/valkey.sock|g' \
  -e 's|^pidfile .*$|pidfile /run/valkey/valkey.pid|g' \
  valkey.conf

sed -i -e 's|^logfile .*$|logfile /var/log/valkey/sentinel.log|g' \
  -e 's|^pidfile .*$|pidfile /run/valkey/sentinel.pid|g' \
  sentinel.conf

%if (%{defined fedora} && 0%{?fedora} < 42) || (%{defined rhel} && 0%{?rhel} < 10)
# these lines are for conditionals around sysconfig to valkey.conf porting scriptlets to avoid re-runs
echo '# valkey_rpm_conf' >> valkey.conf
echo '# valkey-sentinel_rpm_conf' >> sentinel.conf
%endif

%global make_flags DEBUG="" V="echo" PREFIX=%{buildroot}%{_prefix} BUILD_WITH_SYSTEMD=yes BUILD_TLS=yes


%build
%make_build %{make_flags}


%install
%make_install %{make_flags}

# remove sample confs
rm -rf %{buildroot}%{_datadir}/%{name}

# System user
install -p -D -m 0644 %{S:4} %{buildroot}%{_sysusersdir}/%{name}.conf

# Install tmpfiles.d file
install -p -D -m 0644 %{S:5} %{buildroot}%{_tmpfilesdir}/%{name}.conf

# Filesystem.
install -d %{buildroot}%{_sharedstatedir}/%{name}
install -d %{buildroot}%{_localstatedir}/log/%{name}
install -d %{buildroot}%{_localstatedir}/run/%{name}
install -d %{buildroot}%{valkey_modules_dir}

# Install logrotate file.
install -pDm644 %{S:1} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install configuration files.
install -pDm640 %{name}.conf  %{buildroot}%{_sysconfdir}/%{name}/%{name}.conf
install -pDm640 sentinel.conf %{buildroot}%{_sysconfdir}/%{name}/sentinel.conf

# Install systemd unit files.
mkdir -p %{buildroot}%{_unitdir}
install -pm644 %{S:3} %{buildroot}%{_unitdir}
install -pm644 %{S:2} %{buildroot}%{_unitdir}

# Fix non-standard-executable-perm error.
chmod 755 %{buildroot}%{_bindir}/%{name}-*

# Install valkey module header
install -pDm644 src/%{name}module.h %{buildroot}%{_includedir}/%{name}module.h

# Install rpm macros for valkey modules
#mkdir -p %{buildroot}%{_rpmmacrodir}
install -pDm644 %{S:8} %{buildroot}%{_rpmmacrodir}/macros.%{name}

# compat script
install -Dpm 755 %{S:9} %{buildroot}%{_libexecdir}/migrate_redis_to_valkey.sh


%check
%if %{with tests}
# https://github.com/redis/redis/issues/1417 (for "taskset -c 1")
taskset -c 1 ./runtest --clients 50 --skiptest "Active defrag - AOF loading"

# sentinel tests fail in mock, but we want the normal tests above
#./runtest-sentinel
%endif

%pre
%sysusers_create_compat %{S:4}


%post
%systemd_post %{name}.service
%systemd_post %{name}-sentinel.service


%post compat-redis
%{_libexecdir}/migrate_redis_to_valkey.sh


%preun
%systemd_preun %{name}.service
%systemd_preun %{name}-sentinel.service


%postun
%systemd_postun_with_restart %{name}.service
%systemd_postun_with_restart %{name}-sentinel.service


%files
%license COPYING
%license COPYRIGHT-lua
%license COPYING-jemalloc
%license LICENSE-hdrhistogram
%license COPYING-hdrhistogram
%license LICENSE-fpconv
%license COPYING-hiredis-BSD-3-Clause
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%attr(0750, valkey, root) %dir %{_sysconfdir}/%{name}
%attr(0640, valkey, root) %config(noreplace) %{_sysconfdir}/%{name}/%{name}.conf
%attr(0640, valkey, root) %config(noreplace) %{_sysconfdir}/%{name}/sentinel.conf
%dir %{_libdir}/%{name}
%dir %{valkey_modules_dir}
%dir %attr(0750, valkey, valkey) %{_sharedstatedir}/%{name}
%dir %attr(0750, valkey, valkey) %{_localstatedir}/log/%{name}
%{_bindir}/%{name}-*
%{_unitdir}/%{name}.service
%{_unitdir}/%{name}-sentinel.service
%dir %attr(0755, valkey, valkey) %ghost %{_localstatedir}/run/%{name}
%{_sysusersdir}/%{name}.conf
%{_tmpfilesdir}/%{name}.conf


%files devel
# main package is not required
%license COPYING
%{_includedir}/%{name}module.h
%{_rpmmacrodir}/macros.%{name}


%files compat-redis
%{_libexecdir}/migrate_redis_to_valkey.sh
%{_bindir}/redis-*


%changelog
* Tue Sep  9 2025 Remi Collet <remi@fedoraproject.org> - 8.0.4-3
- fix ImageMode: ensure ownership of /etc/valkey

* Fri Aug  1 2025 Remi Collet <remi@fedoraproject.org> - 8.0.4-2
- fix ImageMode: add tmpfiles.d entries for directories below /var

* Wed Jul 16 2025 Remi Collet <remi@fedoraproject.org> - 8.0.4-1
- rebase to 8.0.4 for CVE-2025-27151 CVE-2025-48367 and CVE-2025-32023

* Thu Apr 24 2025 Remi Collet <rcollet@redhat.com> - 8.0.3.1
- rebase to 8.0.3

* Thu Jan 23 2025 Remi Collet <rcollet@redhat.com> - 8.0.2.1
- rebase to 8.0.2
  Resolves: RHEL-73273

* Tue Oct 29 2024 Troy Dawson <tdawson@redhat.com> - 7.2.6-2
- Bump release for October 2024 mass rebuild:
  Resolves: RHEL-64018

* Tue Aug  6 2024 Remi Collet <rcollet@redhat.com> - 7.2.6.1
- rebase to 7.2.6
- merge limit.conf in main service files
- drop /etc/sysconfig/valkey
- rename compat package
- fix working dir
- partially enable upstream test suite

* Mon Jun 24 2024 Troy Dawson <tdawson@redhat.com> - 7.2.5-4
- Bump release for June 2024 mass rebuild

* Mon Apr 22 2024 Nathan Scott <nathans@redhat.com> - 7.2.5-3
- remove version_no_tilde code

* Mon Apr 22 2024 Nathan Scott <nathans@redhat.com> - 7.2.5-2
- move redis compat symlinks to compat subpackage

* Wed Apr 17 2024 Jonathan Wright <jonathan@almalinux.org> - 7.2.5-1
- update to 7.2.5 rhbz#2275379

* Fri Apr 12 2024 Jonathan Wright <jonathan@almalinux.org> - 7.2.5~rc1-2
- add compat subpackage with migration scripts from redis

* Fri Apr 12 2024 Jonathan Wright <jonathan@almalinux.org> - 7.2.5~rc1-1
- update to 7.2.5-rc1

* Tue Apr 09 2024 Jonathan Wright <jonathan@almalinux.org> - 7.2.4~rc1-1
- Initial package build, release candidate
