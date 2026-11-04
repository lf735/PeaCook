// Stubs de macros UVM utilisés par peacook quand la vraie bibliothèque UVM n'est pas fournie.
// Les macros sont neutralisées : l'information architecturale est récupérée autrement
// (analyse syntaxique + lecture du texte brut des classes).
`ifndef PEACOOK_UVM_STUBS
`define PEACOOK_UVM_STUBS
`define uvm_component_utils(T)
`define uvm_component_param_utils(T)
`define uvm_object_utils(T)
`define uvm_object_param_utils(T)
`define uvm_component_utils_begin(T)
`define uvm_component_utils_end
`define uvm_object_utils_begin(T)
`define uvm_object_utils_end
`define uvm_component_param_utils_begin(T)
`define uvm_object_param_utils_begin(T)
`define uvm_field_int(A, F)
`define uvm_field_object(A, F)
`define uvm_field_string(A, F)
`define uvm_field_enum(T, A, F)
`define uvm_field_array_int(A, F)
`define uvm_field_queue_int(A, F)
`define uvm_field_array_object(A, F)
`define uvm_field_queue_object(A, F)
`define uvm_field_sarray_int(A, F)
`define uvm_field_event(A, F)
`define uvm_field_real(A, F)
`define uvm_info(ID, MSG, VERB)
`define uvm_warning(ID, MSG)
`define uvm_error(ID, MSG)
`define uvm_fatal(ID, MSG)
`define uvm_info_context(ID, MSG, VERB, CNTXT)
`define uvm_do(SEQ_OR_ITEM)
`define uvm_do_with(SEQ_OR_ITEM, CONSTRAINTS)
`define uvm_do_pri(SEQ_OR_ITEM, PRIORITY)
`define uvm_do_on(SEQ_OR_ITEM, SEQR)
`define uvm_do_on_with(SEQ_OR_ITEM, SEQR, CONSTRAINTS)
`define uvm_do_on_pri(SEQ_OR_ITEM, SEQR, PRIORITY)
`define uvm_do_on_pri_with(SEQ_OR_ITEM, SEQR, PRIORITY, CONSTRAINTS)
`define uvm_create(SEQ_OR_ITEM)
`define uvm_create_on(SEQ_OR_ITEM, SEQR)
`define uvm_send(SEQ_OR_ITEM)
`define uvm_send_pri(SEQ_OR_ITEM, PRIORITY)
`define uvm_rand_send(SEQ_OR_ITEM)
`define uvm_rand_send_with(SEQ_OR_ITEM, CONSTRAINTS)
`define uvm_declare_p_sequencer(SEQUENCER)
`define uvm_register_cb(T, CB)
`define uvm_set_super_type(T, ST)
`define uvm_analysis_imp_decl(SFX) \
  class uvm_analysis_imp``SFX #(type T=int, type IMP=int); endclass
`define uvm_blocking_put_imp_decl(SFX) \
  class uvm_blocking_put_imp``SFX #(type T=int, type IMP=int); endclass
`define uvm_nonblocking_put_imp_decl(SFX) \
  class uvm_nonblocking_put_imp``SFX #(type T=int, type IMP=int); endclass
`define uvm_put_imp_decl(SFX) \
  class uvm_put_imp``SFX #(type T=int, type IMP=int); endclass
`define uvm_get_imp_decl(SFX) \
  class uvm_get_imp``SFX #(type T=int, type IMP=int); endclass
`define uvm_blocking_get_imp_decl(SFX) \
  class uvm_blocking_get_imp``SFX #(type T=int, type IMP=int); endclass
`endif
