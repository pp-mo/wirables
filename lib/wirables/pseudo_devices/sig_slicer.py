from typing import Literal

from wirables import Device, EventTime, EventValue


class SigSlicer(Device):
    """
    It works with values coded either as a number (integer) or a binary string.
    It provides different modes to control the output update:
        - "all" means the output updates on every input update
        - "change" means only changes in the output value trigger an output update
        - "nonzero" means the output updates only when non-zero (i.e. a pulse trigger)
        - "change_nonzero" updates only when changed AND non-zero
    """

    def __init__(
        self,
        name: str,
        i_bit: int,
        n_bitwidth: int = 1,
        update_trigger_mode: Literal[
            "all", "change", "nonzero", "change_nonzero"
        ] = "change",
        output_name: str = "",
    ):
        super().__init__(name)
        self.i_bit = i_bit
        self.n_bitwidth = n_bitwidth
        self._bitmask = 2**n_bitwidth - 1
        self.update_trigger_mode = update_trigger_mode
        if not output_name:
            output_name = f"{self.name}.output"
        self.output_name = output_name
        self.output = self.add_output(output_name, 0)

    @Device.input
    def inp(self, time: EventTime, value: EventValue):
        old_val = self.output.value
        val = value.value
        input_string = isinstance(value.value, str)
        if input_string:
            val_int = int(val)
            old_val = int(old_val)
        else:
            raise ValueError("string values not yet supported.")
        new_val = (val_int >> self.i_bit) & self._bitmask
        match self.update_trigger_mode:
            case "all":
                # "send through" all updates
                update = True
            case "change":
                # update on value change
                update = new_val != old_val
            case "nonzero":
                # update when nonzero
                update = new_val != 0
            case "change_nonzero":
                # update on value change
                update = new_val not in (old_val, 0)
            case _:
                msg = f"Unexpected trigger mode: {self.update_trigger_mode}"
                raise ValueError(msg)
        if update:
            if input_string:
                out_fmt = f"0{self.n_bitwidth}b"
                new_val = out_fmt.format(new_val)
            self.out(self.output_name, new_val)
