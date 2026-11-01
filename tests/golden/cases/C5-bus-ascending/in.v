// C5: an ascending range keeps its orientation. [0:2] lists bit 0 first, and
// connects leftmost bit to leftmost pin bit, as Verilog does: the library's
// I<2> I<1> I<0> read as I[2:0], so I<2> gets a[0].
module top (a, y, VDD, VSS);
   input [0:2] a;
   output y;
   inout VDD, VSS;

   AND3 u (.I(a), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule
