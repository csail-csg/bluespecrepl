import inspect

def add_line_macro(bsv_code, file_name = None, line_number = None):
    """
    Appends line macro to the provided bsv_code to get accurate BSC error messages.

    If file name or line number are not provided, this function assumes the
    text of bsv_code was written in this function call without line breaks
    between the parenthesis of the function call and bsv_code string. When
    using this function, if you get a compilation error in BSC, the file name
    and line number will point to the file name and line number in the python
    script containing

    Good example:
    >> bsv_code = add_line_macro('''
    module mkTest(Empty);
        Reg#(Bit#(32)) x <- mkReg(0);
    endmodule
    ''')

    Bad example:
    >> bsv_code = 'function Bool inv(Bool x) = !x;'
    >> bsv_code = add_line_macro(bsv_code)
    """

    frame = inspect.stack()[1][0]
    print(str(frame))
    try:
        if not file_name:
            file_name = inspect.getframeinfo(frame).filename
        if not line_number:
            line_number = inspect.getframeinfo(frame).lineno - bsv_code.count('\n')
    finally:
        del frame
    return ('`line %d "%s" 0\n' % (line_number, file_name)) + bsv_code
