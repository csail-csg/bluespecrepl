interface GCD;
    method Action start(Bit#(32) a, Bit#(32) b);
    method Bool result_ready();
    method Bit#(32) result();
    method Action result_deq();
endinterface

typedef enum {ReadyForInput, Busy, OutputReady} GCDState deriving (Bits, Eq, FShow);

module mkGCD(GCD);
    Reg#(GCDState) state <- mkReg(ReadyForInput);
    Reg#(Bit#(32)) x <- mkReg(0);
    Reg#(Bit#(32)) y <- mkReg(0);

    rule swap((state == Busy) && (y > x) && (x != 0));
        x <= y;
        y <= x;
    endrule

    rule subtract((state == Busy) && (x >= y) && (x != 0));
        x <= x - y;
    endrule

    rule finish((state == Busy) && (x == 0));
        state <= OutputReady;
    endrule

    method Action start(Bit#(32) a, Bit#(32) b) if (state == ReadyForInput);
        x <= a;
        y <= b;
        state <= Busy;
    endmethod
    method Bool result_ready();
        return state == OutputReady;
    endmethod
    method Bit#(32) result() if (state == OutputReady);
        return y;
    endmethod
    method Action result_deq() if (state == OutputReady);
        state <= ReadyForInput;
    endmethod
endmodule
