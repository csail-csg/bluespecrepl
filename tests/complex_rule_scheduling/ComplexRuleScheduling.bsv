import FIFO::*;

(* synthesize *)
module mkComplexRuleScheduling(FIFO#(Bit#(8)));
    FIFO#(Bit#(8)) in <- mkComplexPipeline;
    FIFO#(Bit#(8)) middle <- mkComplexPipeline;
    FIFO#(Bit#(8)) out <- mkComplexPipeline;

    rule to_middle;
        middle.enq(in.first + 1);
        in.deq;
    endrule

    rule from_middle;
        out.enq(middle.first + 1);
        middle.deq;
    endrule

    method Bit#(8) first;
        return out.first;
    endmethod

    method Action deq;
        out.deq;
    endmethod

    method Action enq(Bit#(8) x);
        in.enq(x);
    endmethod
endmodule

(* synthesize *)
module mkComplexPipeline(FIFO#(Bit#(8)));
    FIFO#(Bit#(8)) in <- mkPipeline;
    FIFO#(Bit#(8)) middle <- mkPipeline;
    FIFO#(Bit#(8)) out <- mkPipeline;

    rule to_middle;
        middle.enq(in.first + 1);
        in.deq;
    endrule

    rule from_middle;
        out.enq(middle.first + 1);
        middle.deq;
    endrule

    method Bit#(8) first;
        return out.first;
    endmethod

    method Action deq;
        out.deq;
    endmethod

    method Action enq(Bit#(8) x);
        in.enq(x);
    endmethod
endmodule

(* synthesize *)
module mkPipeline(FIFO#(Bit#(8)));
    FIFO#(Bit#(8)) in <- mkLFIFO;
    FIFO#(Bit#(8)) middle <- mkLFIFO;
    FIFO#(Bit#(8)) out <- mkLFIFO;

    rule to_middle;
        middle.enq(in.first + 1);
        in.deq;
    endrule

    rule from_middle;
        out.enq(middle.first + 1);
        middle.deq;
    endrule

    method Bit#(8) first;
        return out.first;
    endmethod

    method Action deq;
        out.deq;
    endmethod

    method Action enq(Bit#(8) x);
        in.enq(x);
    endmethod
endmodule
