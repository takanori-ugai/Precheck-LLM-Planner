"""Offline tests of new exports and the counterfactual execution gate."""
import unittest
from unittest.mock import Mock

import export_revision_completion as export
from replay_aligned_candidates import matched_execution


class RevisionCompletionTests(unittest.TestCase):
    def test_clean_snapshot_audit_and_unique_candidate_count(self):
        from summarize_clean_snapshot import audit
        detail, combined, manifest = audit()
        self.assertEqual(len(detail), 6)
        self.assertEqual(len(combined), 8)
        self.assertEqual(manifest['unique_executed_aligned'], 4)
        self.assertEqual(manifest['unique_vh_successes'], 4)
        self.assertEqual(manifest['unexecuted_cases'], [1, 2, 4, 5])
        self.assertEqual(manifest['api_requests'], 0)

    def test_author_review_export_preserves_ratings_and_limits(self):
        import csv
        import json
        import summarize_semantic_review as review
        outputs = review.build()
        for path, content in outputs.items():
            self.assertEqual(path.read_text(), content)
        manifest = json.loads(outputs[review.FOLDER / 'recorded_results.json'])
        self.assertEqual(manifest['author_records_received'], 8)
        self.assertFalse(manifest['independent_or_blinded'])
        self.assertFalse(manifest['semantic_gold_standard_established'])
        self.assertFalse(manifest['human_labels_generated_or_changed_by_exporter'])
        content = outputs[review.ROOT / 'Paper/appendix-human-review.tex']
        with (review.FOLDER / 'semantic_review.csv').open(newline='') as f:
            for row in csv.DictReader(f):
                self.assertIn(' & '.join(review.tex(row[k]) for k in ('case', 'review_label', 'evidence')), content)
        self.assertLess(content.index('著者の最終記入は'), content.index(r'\begin{table*}'))

    def test_citations_and_reader_facing_paths(self):
        import re
        seen=set(); texts=[]
        def visit(p):
            if p in seen:return
            seen.add(p)
            text=re.sub(r'(?m)^\s*%.*$', '',p.read_text());texts.append(text)
            for child in re.findall(r'\\input\{([^}]+)\}',text):
                q=export.PAPER/child
                visit(q if q.suffix else q.with_suffix('.tex'))
        visit(export.PAPER/'main.tex')
        all_text='\n'.join(texts)
        self.assertNotIn('Paper/',all_text)
        keys=set(re.findall(r'@\w+\{([^,]+),',(export.PAPER/'references.bib').read_text()))
        for group in re.findall(r'\\cite\w*\{([^}]+)\}',all_text):
            for key in group.split(','):self.assertIn(key.strip(),keys)

    def test_review_validation_preserves_pending_and_accepts_dates(self):
        import csv,io,tempfile
        from pathlib import Path
        from validate_unmet_review import validate
        _,blank=export.review_material()
        records=list(csv.DictReader(io.StringIO(blank)))
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'review_blank.csv').write_text(blank)
            (folder/'review.csv').write_text(blank)
            self.assertFalse(validate(folder)['complete'])
            # Synthetic test values are confined to a temporary directory.
            for r in records:r.update(review_label='判断不能',evidence='synthetic test',evaluator='test-only',date='20260907')
            with (folder/'review.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
            self.assertTrue(validate(folder)['complete'])
            (folder/'semantic_review.csv').write_text(blank)
            semantic=validate(folder,review_name='semantic_review.csv')
            self.assertFalse(semantic['complete'])
            self.assertEqual(semantic['review_file'],'semantic_review.csv')
            self.assertIn('form completeness only',semantic['validation_scope'])
            self.assertTrue(validate(folder)['complete'])

    def test_exports_match_saved_inputs(self):
        for path,content in export.build().items():
            self.assertEqual(path.read_text(),content.replace('\r\n','\n'))

    def test_review_blank_targets_unmet_not_human_labels(self):
        import csv,io
        _,blank=export.review_material()
        records=list(csv.DictReader(io.StringIO(blank)))
        self.assertEqual(len(records),8)
        for r in records:
            self.assertEqual(r['phase'],'unmet')
            self.assertTrue(r['unmet_response'])
            self.assertEqual(r['review_label'],'')

    def test_gate_never_executes_mismatch(self):
        expected={'nodes':[{'id':1,'class_name':'character','states':[],'properties':[],
                           'obj_transform':{'position':[0,0,0],'rotation':[0,0,0,1]}}], 'edges':[]}
        observed={'nodes':[],'edges':[]}
        comm=Mock(last_path='before.json');comm.environment_graph.return_value=(True,observed)
        result=matched_execution(comm,expected,'[WALK] <desk> (2)','test',Mock())
        self.assertFalse(result['candidate_executed']);comm.render_script.assert_not_called()

    def test_gate_executes_once_after_match(self):
        expected={'nodes':[{'id':1,'class_name':'character','states':[],'properties':[],
                           'obj_transform':{'position':[0,0,0],'rotation':[0,0,0,1]}}], 'edges':[]}
        comm=Mock(last_path='before.json');comm.environment_graph.return_value=(True,expected)
        comm.render_script.return_value=(False,'returned failure')
        result=matched_execution(comm,expected,'[WALK] <desk> (2)','test',Mock())
        self.assertTrue(result['candidate_executed']);self.assertFalse(result['vh_success'])
        comm.render_script.assert_called_once()


if __name__=='__main__':unittest.main()
