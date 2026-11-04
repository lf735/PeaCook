class bridge_vseq_base extends uvm_sequence;
  `uvm_object_utils(bridge_vseq_base)
  `uvm_declare_p_sequencer(bridge_vseqr)
  function new(string name = "bridge_vseq_base");
    super.new(name);
  endfunction
endclass

class bridge_smoke_vseq extends bridge_vseq_base;
  `uvm_object_utils(bridge_smoke_vseq)
  function new(string name = "bridge_smoke_vseq");
    super.new(name);
  endfunction
  task body();
    apb_cfg_seq cfg_seq;
    stream_seq  data_seq;
    cfg_seq  = apb_cfg_seq::type_id::create("cfg_seq");
    data_seq = stream_seq::type_id::create("data_seq");
    cfg_seq.start(p_sequencer.apb_sqr);
    repeat (8) `uvm_do_on(data_seq, p_sequencer.in_sqr)
  endtask
endclass
