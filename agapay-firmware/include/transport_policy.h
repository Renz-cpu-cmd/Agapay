#pragma once
#ifndef AGAPAY_RELEASE_BUILD
#define AGAPAY_RELEASE_BUILD 0
#endif
#ifndef AGAPAY_LOCAL_DEVELOPMENT
#define AGAPAY_LOCAL_DEVELOPMENT 0
#endif
#if (AGAPAY_RELEASE_BUILD + AGAPAY_LOCAL_DEVELOPMENT) != 1
#error "Select exactly one explicit release or local-development transport profile."
#endif
#if AGAPAY_RELEASE_BUILD && defined(AGAPAY_LOCAL_BENCH_ALERTS) && AGAPAY_LOCAL_BENCH_ALERTS
#error "Cardboard bench outputs cannot be enabled in release firmware."
#endif
constexpr bool transportSame(const char* a,const char* b){return *a==*b&&(*a=='\0'||transportSame(a+1,b+1));}
