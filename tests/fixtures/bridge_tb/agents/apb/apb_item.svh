class apb_item extends uvm_sequence_item;
  rand bit [31:0] addr;
  rand bit [31:0] data;
  rand bit        write;
  constraint c_align { addr[1:0] == 2'b00; }
  `uvm_object_utils_begin(apb_item)
    `uvm_field_int(addr, UVM_ALL_ON)
    `uvm_field_int(data, UVM_ALL_ON)
    `uvm_field_int(write, UVM_ALL_ON)
  `uvm_object_utils_end
  function new(string name = "apb_item");
    super.new(name);
  endfunction
endclass
