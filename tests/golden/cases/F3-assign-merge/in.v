// F3: `assign` between two scalar nets makes them one net. The merged net
// takes the port's name when one side is a port, otherwise the left-hand
// side's, so the .SUBCKT pins stay exactly as declared. Indented the way
// Innovus writes it.
module top (a, y, VDD, VSS);
   input a;
   output y;
   inout VDD;
   inout VSS;
   wire n1;
   wire n2;
   wire n3;

   assign y = n2;
   assign n3 = n1;

   INV u1 (.A(a), .Y(n1), .VDD(VDD), .VSS(VSS));
   INV u2 (.A(n3), .Y(n2), .VDD(VDD), .VSS(VSS));
endmodule
