import unittest
from institutions import parse_table, merge

def xml(value=100, put='', kind='SH'):
    return f'<informationTable xmlns="urn:test"><infoTable><nameOfIssuer>A</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>012345678</cusip><value>{value}</value><sshPrnamt>10</sshPrnamt><sshPrnamtType>{kind}</sshPrnamtType><putCall>{put}</putCall></infoTable></informationTable>'

class Tests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(parse_table(xml(),'2023-01-03')[0][0]['usd'],100)
        self.assertEqual(parse_table(xml(),'2022-12-31')[0][0]['usd'],100000)
    def test_excluded_options_still_reconcile(self):
        self.assertEqual(parse_table(xml(100,'PUT'),'2026-01-01'),([],100))
        self.assertEqual(parse_table(xml(100,kind='PRN'),'2026-01-01'),([],100))
    def test_consolidation(self):
        r=parse_table(xml(),'2026-01-01')[0]
        self.assertEqual(merge(r+r)[0]['usd'],200)
        self.assertEqual(merge(r+r)[0]['shares'],20)

if __name__=='__main__':unittest.main()
