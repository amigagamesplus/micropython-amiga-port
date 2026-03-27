// Port-specific time functions for AmigaOS.
// Included by extmod/modtime.c via MICROPY_PY_TIME_INCLUDEFILE.

#include <time.h>
#include <proto/locale.h>
#include "shared/timeutils/timeutils.h"

// Get timezone offset in seconds (local = utc + offset).
// Uses AmigaOS locale.library: loc_GMTOffset is in minutes, negative = east.
static int32_t amiga_tz_offset_s(void) {
    struct Locale *locale = OpenLocale(NULL);
    if (locale) {
        int32_t offset = -(locale->loc_GMTOffset) * 60;
        CloseLocale(locale);
        return offset;
    }
    return 0;
}

// Get the local time (UTC + timezone offset).
static void mp_time_localtime_get(timeutils_struct_time_t *tm) {
    time_t t = time(NULL) + amiga_tz_offset_s();
    struct tm *gt = gmtime(&t);
    if (gt == NULL) {
        memset(tm, 0, sizeof(*tm));
        tm->tm_year = 1970;
        tm->tm_mon = 1;
        tm->tm_mday = 1;
        return;
    }
    tm->tm_year = gt->tm_year + 1900;
    tm->tm_mon = gt->tm_mon + 1;
    tm->tm_mday = gt->tm_mday;
    tm->tm_hour = gt->tm_hour;
    tm->tm_min = gt->tm_min;
    tm->tm_sec = gt->tm_sec;
    tm->tm_wday = (gt->tm_wday + 6) % 7; // C: Sun=0, MicroPython: Mon=0
    tm->tm_yday = gt->tm_yday + 1;
}

// Return the number of seconds since the Epoch (UTC, no timezone).
static mp_obj_t mp_time_time_get(void) {
    time_t t = time(NULL);
    return mp_obj_new_int((mp_int_t)t);
}
