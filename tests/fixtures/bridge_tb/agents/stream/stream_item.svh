class stream_item extends uvm_sequence_item;
  rand bit [63:0] data[];
  rand bit        last;
  constraint c_len { data.size() inside {[1:16]}; }
  `uvm_object_utils(stream_item)
  function new(string name = "stream_item");
    super.new(name);
  endfunction
endclass
