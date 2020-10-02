#!/usr/bin/env python3

# build HEX font file from FreeDOS CPIDOS font


import os
import sys
import zipfile
import subprocess
import logging
from collections import defaultdict

import monobit

logging.basicConfig(level=logging.INFO)

fdzip = 'cpidos30.zip'
ucp_loc = 'codepage/'
cpi_prefix = 'BIN/'
cpi_names = ['ega.cpx'] + [f'ega{i}.cpx' for i in range(2, 19)]


def main():

    # register custom FreeDOS codepages
    for filename in os.listdir(ucp_loc):
        cp_name, _ = os.path.splitext(os.path.basename(filename))
        monobit.font.Codepage.override(f'cp{cp_name}', f'{os.getcwd()}/{ucp_loc}/{filename}')

    try:
        os.mkdir('work')
    except OSError:
        pass
    os.chdir('work')
    try:
        os.mkdir('yaff')
    except OSError:
        pass
    try:
        os.mkdir('hex')
    except OSError:
        pass

    # unpack zipfile
    pack = zipfile.ZipFile('../' + fdzip, 'r')
    # extract cpi files from compressed cpx files
    for name in cpi_names:
        pack.extract(cpi_prefix + name)
        subprocess.call(['upx', '-d', cpi_prefix + name])


    # load CPIs and add to dictionary
    fonts = {8: {}, 14: {}, 16: {}}
    for cpi_name in cpi_names:
        logging.info(f'Reading {cpi_name}')
        cpi = monobit.load(f'{cpi_prefix}{cpi_name}', format='cpi')
        for font in cpi:
            codepage = font.encoding # always starts with `cp`
            # save intermediate file
            #monobit.Typeface([font]).save(
            #    f'yaff/{cpi_name}_{codepage}_{font.pixel_size:02d}.yaff'
            #)
            height = font.bounding_box[1]
            # resize to allow saving as HEX
            font = font.expand(0, 0, 0, 16-height)
            fonts[font.pixel_size][(cpi_name, codepage)] = font
            # save intermediate file
            monobit.Typeface([font]).save(
                f'hex/{cpi_name}_{codepage}_{font.pixel_size:02d}.hext'
            )

    # retrieve preferred picks from choices file
    logging.info(f'Processing choices')
    choices = defaultdict(list)
    with open('../choices', 'r') as f:
        for line in f:
            if line and line[0] in ('#', '\n'):
                continue
            codepoint, codepagestr = line.strip('\n').split(':', 1)
            label = f'u+{codepoint}'.lower()
            codepage_info = codepagestr.split(':') # e.g. 852:ega.cpx
            if len(codepage_info) > 1:
                codepage, cpi_name = codepage_info[:2]
            else:
                codepage, cpi_name = codepage_info[0], None
            choices[(cpi_name, f'cp{codepage}')].append(label)

    # merge preferred picks
    logging.info(f'Merging choices')
    final_font = {}
    for size, fontdict in fonts.items():
        final_font[size] = monobit.font.Font([])
        for (cpi_name_0, codepage_0), labels in choices.items():
            for (cpi_name_1, codepage_1), font in fontdict.items():
                if (
                        (codepage_0 == codepage_1)
                        and (cpi_name_0 is None or cpi_name_0 == cpi_name_1)
                    ):
                    final_font[size] = final_font[size].merged_with(font.subset(labels))

    # merge other fonts
    logging.info(f'Merging remaining fonts')
    for size, fontdict in fonts.items():
        for font in fontdict.values():
            final_font[size] = final_font[size].merged_with(font)
        monobit.Typeface([final_font[size]]).save(
            f'base_{size:02d}.hex', format='hext'
        )

    # exclude personal use area code points
    logging.info(f'Removing private use keys')
    pua_keys = set(f'u+{_code:04x}' for _code in range(0xe000, 0xf900))
    final_font = {_size: _font.without(pua_keys) for _size, _font in final_font.items()}

    # output
    logging.info(f'Writing output')
    for size, font in final_font.items():
        monobit.Typeface([font]).save(f'base_{size:02d}.hex', format='hext')


main()
