#!/usr/bin/env python3
"""
Test PoT (Program-of-Thoughts) on known failed samples from GPT-4 zeroshot.

This script tests the PoT interpreter on specific failure cases:
1. Temporal average errors (dc5e217a, 7cd3aedf, 22e20f25)
2. Sign errors (1238d807, d7bcc322)

Usage:
    python scripts/test_pot_on_failures.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finbound.reasoning.pot_interpreter import (
    PoTInterpreter,
    PoTProgram,
    PoTStep,
    create_pot_program_for_temporal_average,
    create_pot_program_for_sign_sensitive,
    create_pot_program_for_change_in_averages,
)


def test_temporal_average_dc5e217a():
    """
    Test: dc5e217a - What is the 2019 average free cash flow?
    Gold: 4227.5 = (4,411 + 4,044) / 2
    GPT-4 predicted: 4,411 (wrong - just 2019 value)
    """
    print("\n" + "=" * 60)
    print("Test 1: dc5e217a - 2019 average free cash flow")
    print("=" * 60)

    # Values from evidence
    values_by_year = {
        2018: 4044,
        2019: 4411,
    }

    # Create PoT program
    program = create_pot_program_for_temporal_average(values_by_year, 2019)

    print(f"Question: What is the 2019 average free cash flow?")
    print(f"Values: 2018={values_by_year[2018]}, 2019={values_by_year[2019]}")
    print(f"Expected (Gold): 4227.5")
    print(f"GPT-4 predicted: 4411 (WRONG)")
    print()

    # Execute
    interpreter = PoTInterpreter()
    result = interpreter.execute(program)

    print(f"PoT Program:")
    for step in program.steps:
        print(f"  {step.id}: {step.op} with inputs {step.inputs}")
    print()

    print(f"PoT Result: {result.final_value}")
    print(f"Success: {result.success}")

    # Verify
    expected = 4227.5
    passed = abs(result.final_value - expected) < 0.01
    print(f"PASS: {passed}" + (" ✓" if passed else " ✗"))

    return passed


def test_temporal_average_7cd3aedf():
    """
    Test: 7cd3aedf - What is the 2018 average free cash flow?
    Gold: 3680 = (4,044 + 3,316) / 2
    GPT-4 predicted: 4,044 (wrong - just 2018 value)
    """
    print("\n" + "=" * 60)
    print("Test 2: 7cd3aedf - 2018 average free cash flow")
    print("=" * 60)

    values_by_year = {
        2017: 3316,
        2018: 4044,
    }

    program = create_pot_program_for_temporal_average(values_by_year, 2018)

    print(f"Question: What is the 2018 average free cash flow?")
    print(f"Values: 2017={values_by_year[2017]}, 2018={values_by_year[2018]}")
    print(f"Expected (Gold): 3680")
    print(f"GPT-4 predicted: 4044 (WRONG)")
    print()

    interpreter = PoTInterpreter()
    result = interpreter.execute(program)

    print(f"PoT Result: {result.final_value}")

    expected = 3680
    passed = abs(result.final_value - expected) < 0.01
    print(f"PASS: {passed}" + (" ✓" if passed else " ✗"))

    return passed


def test_change_in_averages_22e20f25():
    """
    Test: 22e20f25 - What is the change between 2018 and 2019 average free cash flow?
    Gold: 547.5 = [(4,411+4,044)/2] - [(4,044+3,316)/2] = 4227.5 - 3680
    GPT-4 predicted: 367 (wrong - simple year-to-year change)
    """
    print("\n" + "=" * 60)
    print("Test 3: 22e20f25 - Change between 2018 and 2019 average FCF")
    print("=" * 60)

    values_by_year = {
        2017: 3316,
        2018: 4044,
        2019: 4411,
    }

    # Create program for change in averages
    program = create_pot_program_for_change_in_averages(values_by_year, 2018, 2019)

    print(f"Question: What is the change between 2018 and 2019 average free cash flow?")
    print(f"Values: 2017={values_by_year[2017]}, 2018={values_by_year[2018]}, 2019={values_by_year[2019]}")
    print(f"Expected (Gold): 547.5 = 4227.5 - 3680")
    print(f"GPT-4 predicted: 367 (WRONG - used simple change)")
    print()

    interpreter = PoTInterpreter()
    result = interpreter.execute(program)

    print(f"PoT Program steps:")
    for step in result.audit_trail:
        print(f"  {step['step_id']}: {step['operation']} = {step['result']}")
    print()

    print(f"PoT Result: {result.final_value}")

    expected = 547.5
    passed = abs(result.final_value - expected) < 0.01
    print(f"PASS: {passed}" + (" ✓" if passed else " ✗"))

    return passed


def test_sign_error_1238d807():
    """
    Test: 1238d807 - What was the increase/(decrease) in Statutory federal income tax from 2018 to 2019?
    Gold: -19411 = 14,694 - 34,105
    GPT-4 predicted: "decrease of $19,411" (qualitative, no sign)
    """
    print("\n" + "=" * 60)
    print("Test 4: 1238d807 - Change in Statutory federal income tax")
    print("=" * 60)

    # Values from derivation: 14,694 - 34,105
    old_value = 34105  # 2018
    new_value = 14694  # 2019

    # Create sign-sensitive program (absolute change)
    program = create_pot_program_for_sign_sensitive(
        operation="absolute_change",
        old_value=old_value,
        new_value=new_value,
        question_asks_decrease=False,  # Question asks for general change
    )

    print(f"Question: What was the increase/(decrease) in Statutory federal income tax from 2018 to 2019?")
    print(f"Values: 2018={old_value}, 2019={new_value}")
    print(f"Expected (Gold): -19411 = 14694 - 34105")
    print(f"GPT-4 predicted: 'decrease of $19,411' (WRONG - qualitative)")
    print()

    interpreter = PoTInterpreter()
    result = interpreter.execute(program)

    print(f"PoT Result: {result.final_value}")

    expected = -19411
    passed = abs(result.final_value - expected) < 0.01
    print(f"PASS: {passed}" + (" ✓" if passed else " ✗"))

    return passed


def test_sign_error_d7bcc322():
    """
    Test: d7bcc322 - What is the difference between Workforce reduction and Facility costs?
    Gold: -1903 = 1,046 - 2,949
    GPT-4 predicted: $1,903 (wrong - dropped sign)
    """
    print("\n" + "=" * 60)
    print("Test 5: d7bcc322 - Difference between Workforce reduction and Facility costs")
    print("=" * 60)

    # Workforce reduction = 1046, Facility costs = 2949
    workforce = 1046
    facility = 2949

    # Create a simple difference program
    program = PoTProgram(
        steps=[
            PoTStep(
                id="diff",
                op="subtract",
                inputs={"a": workforce, "b": facility},
                description="Workforce reduction - Facility costs",
            )
        ],
        final_step="diff",
        metadata={"type": "difference"},
    )

    print(f"Question: What is the difference between Workforce reduction and Facility costs?")
    print(f"Values: Workforce={workforce}, Facility={facility}")
    print(f"Expected (Gold): -1903 = 1046 - 2949")
    print(f"GPT-4 predicted: $1,903 (WRONG - dropped sign)")
    print()

    interpreter = PoTInterpreter()
    result = interpreter.execute(program)

    print(f"PoT Result: {result.final_value}")

    expected = -1903
    passed = abs(result.final_value - expected) < 0.01
    print(f"PASS: {passed}" + (" ✓" if passed else " ✗"))

    return passed


def main():
    print("=" * 60)
    print("PoT (Program-of-Thoughts) Test on GPT-4 Failed Samples")
    print("=" * 60)

    results = []

    # Temporal average tests
    results.append(("dc5e217a - 2019 avg FCF", test_temporal_average_dc5e217a()))
    results.append(("7cd3aedf - 2018 avg FCF", test_temporal_average_7cd3aedf()))
    results.append(("22e20f25 - Change in avg FCF", test_change_in_averages_22e20f25()))

    # Sign error tests
    results.append(("1238d807 - Tax change", test_sign_error_1238d807()))
    results.append(("d7bcc322 - Cost difference", test_sign_error_d7bcc322()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, p in results:
        status = "✓ PASS" if p else "✗ FAIL"
        print(f"  {status}: {name}")

    print()
    print(f"Total: {passed}/{total} passed ({100*passed/total:.1f}%)")

    if passed == total:
        print("\n🎉 All tests passed! PoT correctly handles these failure cases.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
