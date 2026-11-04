class bridge_ref_model extends uvm_component;
  `uvm_component_utils(bridge_ref_model)
  uvm_tlm_analysis_fifo #(stream_item) in_fifo;
  uvm_analysis_port #(stream_item)     ap;
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    in_fifo = new("in_fifo", this);
    ap      = new("ap", this);
  endfunction
  task run_phase(uvm_phase phase);
    stream_item t;
    forever begin
      in_fifo.get(t);
      ap.write(t);
    end
  endtask
endclass
