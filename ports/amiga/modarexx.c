/*
 * modarexx.c - ARexx IPC module for MicroPython AmigaOS port
 *
 * Phase 1: arexx.send() and arexx.exists()
 *
 * Usage from Python:
 *   import arexx
 *
 *   # Check if an ARexx port exists
 *   if arexx.exists("IBROWSE"):
 *       # Send a command (fire & forget)
 *       rc = arexx.send("IBROWSE", "HIDE")
 *
 *       # Send a command and get the result string
 *       rc, result = arexx.send("IBROWSE", "QUERY ITEM=URL", result=True)
 *       print(result)
 *
 *   # List all public ARexx ports
 *   ports = arexx.ports()
 *   for p in ports:
 *       print(p)
 */

#include "py/runtime.h"
#include "py/obj.h"
#include "py/objstr.h"

#include <proto/exec.h>
#include <proto/rexxsyslib.h>
#include <exec/types.h>
#include <exec/ports.h>
#include <exec/memory.h>
#include <rexx/storage.h>
#include <rexx/errors.h>

#include <string.h>

/* ---- Library base ---------------------------------------------------- */

// RexxSysBase is declared as extern struct RxsLib * by proto/rexxsyslib.h.
// We define it here and cast from OpenLibrary's return.
struct RxsLib *RexxSysBase = NULL;

static bool ensure_rexxsys(void) {
    if (RexxSysBase == NULL) {
        RexxSysBase = (struct RxsLib *)OpenLibrary((CONST_STRPTR)"rexxsyslib.library", 0);
        if (RexxSysBase == NULL) {
            mp_raise_msg(&mp_type_OSError,
                MP_ERROR_TEXT("cannot open rexxsyslib.library"));
            return false;
        }
    }
    return true;
}

/* ---- arexx.exists(portname) ------------------------------------------ */
/*
 * Returns True if the named public ARexx port currently exists.
 * Uses Forbid/Permit to safely check the port list.
 */
STATIC mp_obj_t mod_arexx_exists(mp_obj_t portname_obj) {
    const char *portname = mp_obj_str_get_str(portname_obj);
    struct MsgPort *port;

    Forbid();
    port = FindPort((CONST_STRPTR)portname);
    Permit();

    return mp_obj_new_bool(port != NULL);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(mod_arexx_exists_obj, mod_arexx_exists);

/* ---- arexx.send(portname, command, result=False) --------------------- */
/*
 * Send an ARexx command string to the named port.
 *
 * If result=False (default):
 *   Returns the integer RC (0 = success).
 *
 * If result=True:
 *   Returns a tuple (rc, result_string).
 *   result_string is None if the target did not return a RESULT.
 *
 * Raises OSError if:
 *   - rexxsyslib.library cannot be opened
 *   - the target port does not exist
 *   - memory allocation fails
 */
STATIC mp_obj_t mod_arexx_send(size_t n_args, const mp_obj_t *pos_args,
                                mp_map_t *kw_args) {
    /* Parse arguments */
    static const mp_arg_t allowed_args[] = {
        { MP_QSTR_portname, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_command,  MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL} },
        { MP_QSTR_result,   MP_ARG_KW_ONLY  | MP_ARG_BOOL, {.u_bool = false} },
    };

    mp_arg_val_t args[MP_ARRAY_SIZE(allowed_args)];
    mp_arg_parse_all(n_args, pos_args, kw_args,
                     MP_ARRAY_SIZE(allowed_args), allowed_args, args);

    const char *portname = mp_obj_str_get_str(args[0].u_obj);
    const char *command  = mp_obj_str_get_str(args[1].u_obj);
    bool want_result     = args[2].u_bool;

    /* Ensure library is open */
    if (!ensure_rexxsys()) {
        return mp_const_none;  /* unreachable, ensure_rexxsys raises */
    }

    /* Create a private reply port */
    struct MsgPort *replyPort = CreateMsgPort();
    if (replyPort == NULL) {
        mp_raise_msg(&mp_type_OSError,
            MP_ERROR_TEXT("cannot create reply port"));
        return mp_const_none;
    }

    /* Create the RexxMsg */
    struct RexxMsg *rexxMsg = CreateRexxMsg(replyPort, NULL, NULL);
    if (rexxMsg == NULL) {
        DeleteMsgPort(replyPort);
        mp_raise_msg(&mp_type_OSError,
            MP_ERROR_TEXT("cannot create RexxMsg"));
        return mp_const_none;
    }

    /* Create the argument string (the command) */
    rexxMsg->rm_Args[0] = (STRPTR)CreateArgstring((CONST_STRPTR)command, strlen(command));
    if (rexxMsg->rm_Args[0] == NULL) {
        DeleteRexxMsg(rexxMsg);
        DeleteMsgPort(replyPort);
        mp_raise_msg(&mp_type_OSError,
            MP_ERROR_TEXT("cannot create argstring"));
        return mp_const_none;
    }

    /* Set action flags */
    rexxMsg->rm_Action = RXCOMM;
    if (want_result) {
        rexxMsg->rm_Action |= RXFF_RESULT;
    }

    /* Find the target port and send (under Forbid for atomicity) */
    Forbid();
    struct MsgPort *targetPort = FindPort((CONST_STRPTR)portname);
    if (targetPort == NULL) {
        Permit();
        /* Cleanup */
        DeleteArgstring(rexxMsg->rm_Args[0]);
        DeleteRexxMsg(rexxMsg);
        DeleteMsgPort(replyPort);
        mp_raise_msg_varg(&mp_type_OSError,
            MP_ERROR_TEXT("ARexx port '%s' not found"), portname);
        return mp_const_none;
    }
    PutMsg(targetPort, &rexxMsg->rm_Node);
    Permit();

    /* Wait for the reply */
    WaitPort(replyPort);
    GetMsg(replyPort);  /* same pointer as rexxMsg, now filled with results */

    /* Extract results */
    LONG rc = rexxMsg->rm_Result1;
    mp_obj_t result_str = mp_const_none;

    if (want_result && rc == 0 && rexxMsg->rm_Result2 != 0) {
        const char *res_ptr = (const char *)rexxMsg->rm_Result2;
        size_t res_len = strlen(res_ptr);
        /* Try UTF-8 first, fall back to bytes for Latin-1 AmigaOS strings */
        nlr_buf_t nlr;
        if (nlr_push(&nlr) == 0) {
            result_str = mp_obj_new_str(res_ptr, res_len);
            nlr_pop();
        } else {
            /* UnicodeError: return as bytes instead */
            result_str = mp_obj_new_bytes((const byte *)res_ptr, res_len);
        }
        DeleteArgstring((UBYTE *)rexxMsg->rm_Result2);
    }

    /* Cleanup */
    DeleteArgstring(rexxMsg->rm_Args[0]);
    DeleteRexxMsg(rexxMsg);
    DeleteMsgPort(replyPort);

    /* Return value */
    if (want_result) {
        mp_obj_t tuple[2];
        tuple[0] = mp_obj_new_int(rc);
        tuple[1] = result_str;
        return mp_obj_new_tuple(2, tuple);
    } else {
        return mp_obj_new_int(rc);
    }
}
STATIC MP_DEFINE_CONST_FUN_OBJ_KW(mod_arexx_send_obj, 2, mod_arexx_send);

/* ---- arexx.ports() --------------------------------------------------- */
/*
 * Returns a list of all currently registered public port names.
 * This is useful for discovering which ARexx-aware applications are running.
 * Note: the list is a snapshot; ports may appear/disappear at any time.
 */
STATIC mp_obj_t mod_arexx_ports(void) {
    mp_obj_t port_list = mp_obj_new_list(0, NULL);
    struct Node *node;

    Forbid();
    struct List *pubPortList = &SysBase->PortList;
    for (node = pubPortList->lh_Head; node->ln_Succ; node = node->ln_Succ) {
        if (node->ln_Name != NULL) {
            mp_obj_t name = mp_obj_new_str(node->ln_Name,
                                           strlen(node->ln_Name));
            mp_obj_list_append(port_list, name);
        }
    }
    Permit();

    return port_list;
}
STATIC MP_DEFINE_CONST_FUN_OBJ_0(mod_arexx_ports_obj, mod_arexx_ports);

/* ---- Module cleanup (called from main.c _exit path) ------------------- */

void mod_arexx_deinit(void) {
    if (RexxSysBase != NULL) {
        CloseLibrary((struct Library *)RexxSysBase);
        RexxSysBase = NULL;
    }
}

/* ---- Module definition ------------------------------------------------ */

STATIC const mp_rom_map_elem_t arexx_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_arexx) },
    { MP_ROM_QSTR(MP_QSTR_send),     MP_ROM_PTR(&mod_arexx_send_obj) },
    { MP_ROM_QSTR(MP_QSTR_exists),   MP_ROM_PTR(&mod_arexx_exists_obj) },
    { MP_ROM_QSTR(MP_QSTR_ports),    MP_ROM_PTR(&mod_arexx_ports_obj) },
};
STATIC MP_DEFINE_CONST_DICT(arexx_module_globals, arexx_module_globals_table);

const mp_obj_module_t mp_module_arexx = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&arexx_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_arexx, mp_module_arexx);
