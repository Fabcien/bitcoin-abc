#!/usr/bin/env python3
# Copyright (c) 2023 The Bitcoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""
Test Chronik's /script/:type/:payload/confirmed-txs endpoint.
"""

import http.client

from test_framework.address import (
    ADDRESS_ECREG_P2SH_OP_TRUE,
    P2SH_OP_TRUE,
    SCRIPTSIG_OP_TRUE,
)
from test_framework.blocktools import (
    GENESIS_BLOCK_HASH,
    GENESIS_CB_TXID,
    TIME_GENESIS_BLOCK,
    create_block,
    create_coinbase,
)
from test_framework.messages import COutPoint, CTransaction, CTxIn, CTxOut
from test_framework.p2p import P2PDataStore
from test_framework.test_framework import BitcoinTestFramework
from test_framework.txtools import pad_tx
from test_framework.util import assert_equal, iter_chunks


class ChronikScriptConfirmedTxsTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [['-chronik']]

    def skip_test_if_missing_module(self):
        self.skip_if_no_chronik()

    def run_test(self):
        import chronik_pb2 as pb

        def query_script_txs(script_type, payload_hex, page=None, page_size=None):
            chronik_port = self.nodes[0].chronik_port
            client = http.client.HTTPConnection('127.0.0.1', chronik_port, timeout=4)
            url = f'/script/{script_type}/{payload_hex}/confirmed-txs'
            if page is not None:
                url += f'?page={page}'
            if page_size is not None:
                url += f'&page_size={page_size}'
            client.request('GET', url)
            response = client.getresponse()
            assert_equal(response.getheader('Content-Type'),
                         'application/x-protobuf')
            return response

        def query_script_txs_success(*args, **kwargs):
            response = query_script_txs(*args, **kwargs)
            assert_equal(response.status, 200)
            proto_tx = pb.TxHistoryPage()
            proto_tx.ParseFromString(response.read())
            return proto_tx

        def query_script_txs_err(*args, status, **kwargs):
            response = query_script_txs(*args, **kwargs)
            assert_equal(response.status, status)
            proto_error = pb.Error()
            proto_error.ParseFromString(response.read())
            return proto_error

        node = self.nodes[0]
        peer = node.add_p2p_connection(P2PDataStore())
        mocktime = 1300000000
        node.setmocktime(mocktime)

        assert_equal(
            query_script_txs_err('', '', status=400).msg,
            '400: Unknown script type: ')
        assert_equal(
            query_script_txs_err('foo', '', status=400).msg,
            '400: Unknown script type: foo')
        assert_equal(
            query_script_txs_err('p2pkh', 'LILALI', status=400).msg,
            "400: Invalid hex: Invalid character 'L' at position 0")
        assert_equal(
            query_script_txs_err('other', 'LILALI', status=400).msg,
            "400: Invalid hex: Invalid character 'L' at position 0")
        assert_equal(
            query_script_txs_err('p2pkh', '', status=400).msg,
            '400: Invalid payload for P2PKH: Invalid length, ' +
            'expected 20 bytes but got 0 bytes')
        assert_equal(
            query_script_txs_err('p2pkh', 'aA', status=400).msg,
            '400: Invalid payload for P2PKH: Invalid length, ' +
            'expected 20 bytes but got 1 bytes')
        assert_equal(
            query_script_txs_err('p2sh', 'aaBB', status=400).msg,
            '400: Invalid payload for P2SH: Invalid length, ' +
            'expected 20 bytes but got 2 bytes')
        assert_equal(
            query_script_txs_err('p2pk', 'aaBBcc', status=400).msg,
            '400: Invalid payload for P2PK: Invalid length, ' +
            'expected one of [33, 65] but got 3 bytes')

        genesis_pk = (
            '04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6'
            'bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f'
        )

        assert_equal(
            query_script_txs_err(
                'p2pk', genesis_pk, status=400, page=0, page_size=201).msg,
            '400: Requested page size 201 is too big, maximum is 200')
        assert_equal(
            query_script_txs_err(
                'p2pk', genesis_pk, status=400, page=0, page_size=0).msg,
            '400: Requested page size 0 is too small, minimum is 1')
        assert_equal(
            query_script_txs_err(
                'p2pk', genesis_pk, status=400, page=0, page_size=2**32).msg,
            '400: Invalid param page_size: 4294967296, ' +
            'number too large to fit in target type')
        assert_equal(
            query_script_txs_err(
                'p2pk', genesis_pk, status=400, page=2**32, page_size=1).msg,
            '400: Invalid param page: 4294967296, ' +
            'number too large to fit in target type')

        # Handle overflow gracefully on 32-bit
        assert_equal(
            query_script_txs_success(
                'p2pk', genesis_pk, page=2**32 - 1, page_size=200),
            pb.TxHistoryPage(num_pages=1, num_txs=1))

        genesis_cb_script = bytes.fromhex(f'41{genesis_pk}ac')
        genesis_tx = pb.Tx(
            txid=bytes.fromhex(GENESIS_CB_TXID)[::-1],
            version=1,
            inputs=[pb.TxInput(
                prev_out=pb.OutPoint(txid=bytes(32), out_idx=0xffffffff),
                input_script=(
                    b'\x04\xff\xff\x00\x1d\x01\x04EThe Times 03/Jan/2009 Chancellor '
                    b'on brink of second bailout for banks'
                ),
                sequence_no=0xffffffff,
            )],
            outputs=[pb.TxOutput(
                value=5000000000,
                output_script=genesis_cb_script,
            )],
            lock_time=0,
            block=pb.BlockMetadata(
                hash=bytes.fromhex(GENESIS_BLOCK_HASH)[::-1],
                height=0,
                timestamp=TIME_GENESIS_BLOCK,
            ),
            time_first_seen=0,
            is_coinbase=True,
        )

        genesis_db_script_history = query_script_txs_success('p2pk', genesis_pk)
        assert_equal(
            genesis_db_script_history,
            pb.TxHistoryPage(
                txs=[genesis_tx],
                num_pages=1,
                num_txs=1))

        script_type = 'p2sh'
        payload_hex = P2SH_OP_TRUE[2:-1].hex()

        # Generate 101 blocks to some address and verify pages
        blockhashes = self.generatetoaddress(node, 101, ADDRESS_ECREG_P2SH_OP_TRUE)

        def check_confirmed_txs(txs, *, page_size=25):
            pages = list(iter_chunks(txs, page_size))
            for page_num, page_txs in enumerate(pages):
                script_history = query_script_txs_success(
                    script_type, payload_hex, page=page_num, page_size=page_size)
                for tx_idx, entry in enumerate(page_txs):
                    script_tx = script_history.txs[tx_idx]
                    if 'txid' in entry:
                        assert_equal(script_tx.txid[::-1].hex(), entry['txid'])
                    if 'block' in entry:
                        block_height, block_hash = entry['block']
                        assert_equal(script_tx.block, pb.BlockMetadata(
                            hash=bytes.fromhex(block_hash)[::-1],
                            height=block_height,
                            timestamp=script_tx.block.timestamp,
                        ))

        txs = [{'block': (i + 1, blockhash)} for i, blockhash in enumerate(blockhashes)]
        check_confirmed_txs(txs)
        check_confirmed_txs(txs, page_size=200)

        # Undo last block & check history
        node.invalidateblock(blockhashes[-1])
        check_confirmed_txs(txs[:-1])
        check_confirmed_txs(txs[:-1], page_size=200)

        # Create 1 block manually
        coinbase_tx = create_coinbase(101)
        coinbase_tx.vout[0].scriptPubKey = P2SH_OP_TRUE
        coinbase_tx.rehash()
        block = create_block(int(blockhashes[-2], 16),
                             coinbase_tx,
                             mocktime + 1000)
        block.solve()
        peer.send_blocks_and_test([block], node)
        blockhashes[-1] = block.hash

        txs = [{'block': (i + 1, blockhash)} for i, blockhash in enumerate(blockhashes)]
        check_confirmed_txs(txs)
        check_confirmed_txs(txs, page_size=200)

        # Generate 900 more blocks and verify
        # Total of 1001 txs for this script (a page in the DB is 1000 entries long)
        blockhashes += self.generatetoaddress(node, 900, ADDRESS_ECREG_P2SH_OP_TRUE)
        txs = [{'block': (i + 1, blockhash)} for i, blockhash in enumerate(blockhashes)]
        page_sizes = [1, 5, 7, 25, 111, 200]
        for page_size in page_sizes:
            check_confirmed_txs(txs, page_size=page_size)

        coinvalue = 5000000000
        cointxids = []
        for coinblockhash in blockhashes[:10]:
            coinblock = node.getblock(coinblockhash)
            cointxids.append(coinblock['tx'][0])

        mempool_txids = []
        for cointxid in cointxids:
            tx = CTransaction()
            tx.nVersion = 1
            tx.vin = [CTxIn(outpoint=COutPoint(int(cointxid, 16), 0),
                            scriptSig=SCRIPTSIG_OP_TRUE)]
            tx.vout = [CTxOut(coinvalue - 1000, P2SH_OP_TRUE)]
            pad_tx(tx)
            txid = node.sendrawtransaction(tx.serialize().hex())
            mempool_txids.append(txid)

        # confirmed-txs completely unaffected by mempool txs
        for page_size in page_sizes:
            check_confirmed_txs(txs, page_size=page_size)

        # Mine mempool txs, now they're in confirmed-txs
        newblockhash = self.generatetoaddress(node, 1, ADDRESS_ECREG_P2SH_OP_TRUE)[0]
        txs.append({'block': (1002, newblockhash)})
        txs += [{'block': (1002, newblockhash), 'txid': txid}
                for txid in sorted(mempool_txids)]
        for page_size in page_sizes:
            check_confirmed_txs(txs, page_size=page_size)


if __name__ == '__main__':
    ChronikScriptConfirmedTxsTest().main()