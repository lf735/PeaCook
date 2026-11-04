class bridge_vseqr extends uvm_sequencer;
  `uvm_component_utils(bridge_vseqr)
  apb_sequencer    apb_sqr;
  stream_sequencer in_sqr;
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
endclass
