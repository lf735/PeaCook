"""Base de connaissances sur les classes standard UVM : rôle, ports hérités, paramètre de transaction."""
from __future__ import annotations

# classe de base UVM -> rôle
ROLE_BY_BASE = {
    "uvm_test": "test", "uvm_env": "env", "uvm_agent": "agent", "uvm_driver": "driver",
    "uvm_push_driver": "driver", "uvm_monitor": "monitor", "uvm_scoreboard": "scoreboard",
    "uvm_subscriber": "subscriber", "uvm_sequencer": "sequencer", "uvm_sequencer_base": "sequencer",
    "uvm_sequencer_param_base": "sequencer", "uvm_reg_predictor": "predictor",
    "uvm_tlm_analysis_fifo": "fifo", "uvm_tlm_fifo": "fifo", "uvm_tlm_fifo_base": "fifo",
    "uvm_component": "component", "uvm_sequence_item": "seq_item", "uvm_sequence": "sequence",
    "uvm_sequence_base": "sequence", "uvm_object": "object", "uvm_reg_block": "reg_block",
    "uvm_reg_adapter": "reg_adapter", "uvm_reg": "reg", "uvm_reg_map": "reg_map", "uvm_reg_field": "reg_field",
    "uvm_callback": "callback", "uvm_transaction": "seq_item", "uvm_report_object": "component",
    "uvm_reg_sequence": "sequence", "uvm_mem": "reg_mem", "uvm_reg_file": "reg_file",
    "uvm_in_order_comparator": "scoreboard", "uvm_in_order_class_comparator": "scoreboard",
    "uvm_algorithmic_comparator": "scoreboard", "uvm_random_stimulus": "component",
    "uvm_event_pool": "object", "uvm_event": "object",
}

COMPONENT_BASES = {"uvm_component", "uvm_test", "uvm_env", "uvm_agent", "uvm_driver", "uvm_push_driver",
                   "uvm_monitor", "uvm_scoreboard", "uvm_subscriber", "uvm_sequencer", "uvm_sequencer_base",
                   "uvm_sequencer_param_base", "uvm_reg_predictor", "uvm_tlm_analysis_fifo", "uvm_tlm_fifo",
                   "uvm_tlm_fifo_base", "uvm_report_object", "uvm_in_order_comparator",
                   "uvm_in_order_class_comparator", "uvm_algorithmic_comparator", "uvm_random_stimulus"}

# classe de base -> [(nom du port, kind, protocole, index du paramètre de transaction ou None)]
KB_PORTS = {
    "uvm_driver": [("seq_item_port", "port", "seq_item", 0)],
    "uvm_push_driver": [("req_export", "export", "put", 0)],
    "uvm_sequencer": [("seq_item_export", "export", "seq_item", 0)],
    "uvm_sequencer_param_base": [("seq_item_export", "export", "seq_item", 0)],
    "uvm_subscriber": [("analysis_export", "imp", "analysis", 0)],
    "uvm_tlm_analysis_fifo": [("analysis_export", "imp", "analysis", 0), ("get_peek_export", "export", "get_peek", 0),
                              ("put_export", "export", "put", 0)],
    "uvm_tlm_fifo": [("put_export", "export", "put", 0), ("get_peek_export", "export", "get_peek", 0)],
    "uvm_reg_predictor": [("bus_in", "imp", "analysis", 0), ("reg_ap", "port", "analysis", None)],
    "uvm_in_order_comparator": [("before_export", "imp", "analysis", 0), ("after_export", "imp", "analysis", 0)],
    "uvm_in_order_class_comparator": [("before_export", "imp", "analysis", 0), ("after_export", "imp", "analysis", 0)],
}

PORT_TYPE_RE = r"^(uvm_(?:blocking_|nonblocking_)?(?:analysis|put|get|peek|get_peek|transport|master|slave|seq_item_pull|seq_item_push)(?:_[a-z]+)?_(?:port|export|imp)(?:_\w+)?|uvm_analysis_imp\w*|uvm_\w+_imp_\w+)$"

# types qui sont des "ports" (jamais des composants enfants)
PORT_PREFIXES = ("uvm_analysis_", "uvm_blocking_", "uvm_nonblocking_", "uvm_put_", "uvm_get_", "uvm_peek_",
                 "uvm_get_peek_", "uvm_transport_", "uvm_master_", "uvm_slave_", "uvm_seq_item_")
FIFO_TYPES = {"uvm_tlm_fifo", "uvm_tlm_analysis_fifo"}

ENUMS = {"UVM_ACTIVE": 1, "UVM_PASSIVE": 0, "UVM_NONE": 0, "UVM_LOW": 100, "UVM_MEDIUM": 200, "UVM_HIGH": 300,
         "UVM_FULL": 400, "UVM_DEBUG": 500, "UVM_NO_ACTION": 0, "UVM_LITTLE_ENDIAN": 0, "UVM_BIG_ENDIAN": 1,
         "UVM_ALL_ON": 0x55, "UVM_DEFAULT": 0x555, "UVM_NO_COVERAGE": 0, "UVM_CVR_ALL": 15}

# couleurs (palette partagée entre rendus)
ROLE_COLORS = {
    "test": "#e8d5f5", "env": "#d5e8f5", "agent": "#d5f5e3", "driver": "#fdebd0", "monitor": "#fcf3cf",
    "sequencer": "#fadbd8", "virtual_sequencer": "#f5b7b1", "scoreboard": "#d6eaf8", "subscriber": "#e8f8f5",
    "predictor": "#e8f8f5", "fifo": "#f2f3f4", "component": "#ececec", "reg_block": "#ebdef0",
    "reg_adapter": "#ebdef0", "ref_model": "#d1f2eb", "dut": "#fdfefe", "interface": "#fef9e7",
    "sequence": "#fef5e7", "virtual_sequence": "#fdebd0", "seq_item": "#f8f9f9", "object": "#f8f9f9",
    "config": "#f4ecf7", "callback": "#f8f9f9",
}
