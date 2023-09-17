/**
 * @generated by contrib/devtools/chainparams/generate_chainparams_constants.py
 */

#include <chainparamsconstants.h>

namespace ChainParamsConstants {
    const BlockHash MAINNET_DEFAULT_ASSUME_VALID = BlockHash::fromHex("0000000000000000035571d03330a6a5f9e36dc6b279c1e269f5c8bd1b8f9333");
    const uint256 MAINNET_MINIMUM_CHAIN_WORK = uint256S("0000000000000000000000000000000000000000016916c574b4e382c788daf9");
    const uint64_t MAINNET_ASSUMED_BLOCKCHAIN_SIZE = 211;
    const uint64_t MAINNET_ASSUMED_CHAINSTATE_SIZE = 3;

    const BlockHash TESTNET_DEFAULT_ASSUME_VALID = BlockHash::fromHex("0000000001ef45e07fc7d2918c689a7e995fba24124ecc0f449632b17554eec1");
    const uint256 TESTNET_MINIMUM_CHAIN_WORK = uint256S("00000000000000000000000000000000000000000000006e9e42b8468784a16e");
    const uint64_t TESTNET_ASSUMED_BLOCKCHAIN_SIZE = 55;
    const uint64_t TESTNET_ASSUMED_CHAINSTATE_SIZE = 2;
} // namespace ChainParamsConstants

