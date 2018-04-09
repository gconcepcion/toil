# Copyright (C) 2018 UCSC Computational Genomics Lab
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

import argparse
import os
import logging

from toil import subprocess
from toil.wdl.wdl_interpret import InterpretWDL, recursive_glob, generate_docker_bashscript_file, heredoc_wdl
from toil.wdl.wdl_compile import CompileWDL
import toil.wdl.wdl_parser as wdl_parser

wdllogger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Runs WDL files with toil.')
    parser.add_argument('wdl_file', help='A WDL workflow file.')
    parser.add_argument('secondary_file', help='A secondary data file (json).')
    parser.add_argument('-o',
                        '--output_directory',
                        required=False,
                        default=os.getcwd(),
                        help='Optionally specify the directory that outputs '
                             'are written to.  Default is the current working dir.')
    parser.add_argument('--gen_parse_files', required=False, default=False,
                        help='Creates "AST.out", which holds the printed AST and'
                             '"mappings.out", which holds the printed task, workflow,'
                             'csv, and tsv dictionaries generated by the parser.')
    parser.add_argument('--dont_delete_compiled', required=False, default=False,
                        help='Saves the compiled toil script generated from the'
                             'wdl/json files from deletion.')

    # wdl_run_args is an array containing all of the unknown arguments not
    # specified by the parser in this main.  All of these will be passed down in
    # check_call later to run the compiled toil file.
    args, wdl_run_args = parser.parse_known_args()

    wdl_file_path = os.path.abspath(args.wdl_file)
    args.secondary_file = os.path.abspath(args.secondary_file)
    args.output_directory = os.path.abspath(args.output_directory)

    iWDL = InterpretWDL(wdl_file_path, args.secondary_file, args.output_directory)

    # read secondary file; create dictionary to hold variables
    if args.secondary_file.endswith('.json'):
        iWDL.dict_from_JSON(args.secondary_file)
    elif args.secondary_file.endswith('.yml') or args.secondary_file.endswith('.yaml'):
        iWDL.dict_from_YML(args.secondary_file) # json only atm
    else:
        raise RuntimeError('Unsupported Secondary File Type.  Use json.')

    # parse the wdl AST into 2 dictionaries
    with open(wdl_file_path, 'r') as wdl:
        wdl_string = wdl.read()
        ast = wdl_parser.parse(wdl_string).ast()
        iWDL.create_tasks_dict(ast)
        iWDL.create_workflows_dict(ast)

    cWDL = CompileWDL(iWDL.tasks_dictionary,
                      iWDL.workflows_dictionary,
                      args.output_directory,
                      iWDL.json_dict,
                      iWDL.tsv_dict,
                      iWDL.csv_dict)

    # use the AST dictionaries to write 4 strings
    # these are the future 4 sections of the compiled toil python file
    module_section = cWDL.write_modules()
    fn_section = cWDL.write_functions()
    main_section = cWDL.write_main()

    # write 3 strings to a python output file
    cWDL.write_python_file(module_section,
                           fn_section,
                           main_section,
                           cWDL.output_file)

    wdllogger.debug('WDL file compiled to toil script.  Running now.')

    if args.gen_parse_files:
        cWDL.write_mappings(iWDL)
        cWDL.write_AST()

    cmd = ['python', cWDL.output_file]
    cmd.extend(wdl_run_args)
    subprocess.check_call(cmd)

    if not args.dont_delete_compiled:
        os.remove(cWDL.output_file)

if __name__ == '__main__':
    main()