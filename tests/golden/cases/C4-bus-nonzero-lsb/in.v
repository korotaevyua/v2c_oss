// C4: a bus whose LSB is not 0. Indices stay as declared, and a part select
// maps onto a submodule's bus port bit by bit, MSB first.
module pair (a, y, VDD, VSS);
   input [1:0] a;
   output y;
   inout VDD, VSS;

   NAND2 g (.A(a[1]), .B(a[0]), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule

module top (d, y, VDD, VSS);
   input [7:4] d;
   output y;
   inout VDD, VSS;

   pair u (.a(d[6:5]), .y(y), .VDD(VDD), .VSS(VSS));
endmodule
