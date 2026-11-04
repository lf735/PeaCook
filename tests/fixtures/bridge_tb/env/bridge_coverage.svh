class bridge_coverage extends uvm_subscriber #(apb_item);
  `uvm_component_utils(bridge_coverage)
  apb_item item;
  covergroup cg_reg;
    cp_addr : coverpoint item.addr;
    cp_wr   : coverpoint item.write;
  endgroup
  function new(string name, uvm_component parent);
    super.new(name, parent);
    cg_reg = new();
  endfunction
  function void write(apb_item t);
    item = t;
    cg_reg.sample();
  endfunction
endclass
