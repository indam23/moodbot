from typing import Dict, List, Optional
import logging
import json
import pandas as pd

logger = logging.getLogger(__file__)


class NLUEvaluationResult:
    def __init__(self, name, report_filepath="", label_name=""):
        self.report_filepath = report_filepath
        self.name = name
        self.label_name = label_name
        self.report = self.load_report_from_file()
        self.df = self.load_df()

    def load_report_from_file(self) -> Dict:
        try:
            with open(self.report_filepath, "r") as f:
                report = json.loads(f.read())
        except FileNotFoundError:
            report = {}
        return report

    def load_report_from_df(self) -> Dict:
        report = self.df.T.to_dict()
        return report

    def load_df(self):
        df = pd.DataFrame.from_dict(self.report).transpose()
        df.name = self.name
        df = self.drop_excluded_classes(df)
        return self.set_index_names(df)

    def set_index_names(self, df):
        df = df[:]
        df.columns.set_names("metric", inplace=True)
        df.index.set_names(self.label_name, inplace=True)
        return df

    @classmethod
    def remove_excluded_classes(cls, classes):
        for excluded_class in ["accuracy"]:
            try:
                classes.remove(excluded_class)
            except:
                pass
        return classes

    @classmethod
    def drop_excluded_classes(cls, df):
        for excluded_class in ["accuracy"]:
            try:
                df = df.drop(excluded_class)
            except:
                pass
        return df

    @classmethod
    def drop_non_numeric_metrics(cls, df):
        for non_numeric_metric in ["confused_with"]:
            try:
                df = df.drop(columns=non_numeric_metric)
            except:
                pass
        return df

    @classmethod
    def sort_by_support(cls, df):
        return df.sort_values(by="support", ascending=False)

    @classmethod
    def create_html_table(cls, df: pd.DataFrame, columns=None):
        if not columns:
            columns = df.columns
        html_table = df[columns].to_html()
        return html_table




class CombinedNLUEvaluationResults(NLUEvaluationResult):
    def __init__(
        self,
        name,
        result_sets_to_combine: Optional[List[NLUEvaluationResult]] = None,
        label_name="",
    ):
        self.name = name
        if not result_sets_to_combine:
            result_sets_to_combine = []
        self.result_sets = result_sets_to_combine
        self.label_name = label_name
        self.df = self.load_joined_df()
        self.report = self.load_joined_report()

    def load_joined_df(self) -> pd.DataFrame:
        if not self.result_sets:
            columns = pd.MultiIndex(levels=[[], []], codes=[[], []])
            index = pd.Index([])
            joined_df = pd.DataFrame(index=index, columns=columns)
        else:
            joined_df = pd.concat(
                [result.df for result in self.result_sets],
                axis=1,
                keys=[result.name for result in self.result_sets],
            )
        self.drop_excluded_classes(joined_df)
        return self.set_index_names(joined_df)

    def set_index_names(self, joined_df):
        joined_df = joined_df.swaplevel(axis="columns")
        joined_df.columns.set_names(["metric", "result_set"], inplace=True)
        joined_df.index.set_names([self.label_name], inplace=True)

        return joined_df

    def load_joined_report(self):
        report = {
            label: {
                metric: self.df.loc[label].xs(metric).to_dict()
                for metric in self.df.loc[label].index.get_level_values("metric")
                if label
            }
            for label in self.df.index
        }
        return report

    def load_result_sets_from_df(self):
        result_sets = []
        for result_set_name in self.df.columns.get_level_values("result_set"):
            result = NLUEvaluationResult(
                name=result_set_name, label_name=self.label_name
            )
            result.df = self.df.swaplevel(axis=1)[result_set_name]
            result.report = result.load_report_from_df()
            result_sets.append(result)
        return result_sets

    @classmethod
    def drop_non_numeric_metrics(cls, df):
        for non_numeric_metric in ["confused_with"]:
            try:
                df = df.drop(columns=non_numeric_metric, level="metric")
            except:
                pass
        return df

    @classmethod
    def sort_by_support(cls, df):
        return df.sort_values(
            by=[("support", df["support"].iloc[:, 0].name)],
            ascending=False
        )

    @classmethod
    def order_metrics(cls, df, metrics_order=None):
        if not metrics_order:
            metrics_order = df.columns.get_level_values("metric")
        metrics_order_dict = {v: k for k, v in enumerate(metrics_order)}
        df = df.sort_index(
            axis=1,
            level="metric",
            key=lambda index: pd.Index(
                [metrics_order_dict.get(x) for x in index], name="metric"
            ),
            sort_remaining=False,
        )
        return df

    @classmethod
    def order_result_sets(cls, df, result_set_order=None):
        if not result_set_order:
            result_set_order = [result.name for result in df.columns.get_level_values("result_set")]
        result_set_order_dict = {v: k for k, v in enumerate(result_set_order)}
        df.sort_index(
            axis="columns",
            level="result_set",
            key=lambda index: pd.Index(
                [result_set_order_dict.get(x) for x in index], name="result_set"
            ),
            sort_remaining=False,
        )
        return df

    def write_combined_json_report(self, filepath):
        with open(filepath, "w+") as fh:
            json.dump(self.report, fh, indent=2)

    def load_df_from_report(self):
        joined_df = pd.DataFrame.from_dict(
            {
                (label, metric): self.report[label][metric]
                for label in self.report.keys()
                for metric in self.report[label].keys()
            },
            orient="index",
        ).unstack()
        return self.set_index_names(joined_df)

    @classmethod
    def load_from_combined_json_report(cls, filepath, label_name):
        combined_results = cls(label_name=label_name)
        with open(filepath, "r") as fh:
            combined_results.report = json.load(fh)
        combined_results.df = combined_results.load_df_from_report()
        combined_results.result_sets = combined_results.load_result_sets_from_df()
        return combined_results

    def get_diff_df(self, result_set_name_for_base_of_comparison=None, metrics_to_diff=None):
        if not result_set_name_for_base_of_comparison:
            result_set_name_for_base_of_comparison = self.result_sets[0].name
        if not metrics_to_diff:
            metrics_to_diff = list(set(self.df.columns.get_level_values("metric")))

        def diff_from_base(x):
            metric = x.name[0]
            if metric == "confused_with":
                return
            if metric == "support":
                return x.fillna(0) - self.df[(metric, result_set_name_for_base_of_comparison)].fillna(0)
            return x-self.df[(metric, result_set_name_for_base_of_comparison)]


        diff_df = self.df[metrics_to_diff].apply(diff_from_base)
        diff_df.drop(columns=result_set_name_for_base_of_comparison, level=1, inplace=True)
        diff_df = self.drop_non_numeric_metrics(diff_df)
        diff_df.rename(columns=lambda col: f"({col} - {result_set_name_for_base_of_comparison})", level=1, inplace=True)
        return diff_df

    def show_labels_with_changes(self):
        diff_df = self.get_diff_df()
        rows_with_changes = (diff_df != 0).any(axis=1)
        df = self.df.loc[rows_with_changes]
        diff_df_selected = diff_df.loc[rows_with_changes]
        combined_diff_df = pd.concat([df, diff_df_selected], axis=1)
        return combined_diff_df


if __name__ == "__main__":
    a = NLUEvaluationResult("a", "results/1/intent_report.json", "intent")
    b = NLUEvaluationResult("b", "results/2/intent_report.json", "intent")

    combined_results = CombinedNLUEvaluationResults("Intent Evaluation Comparison", [a, b], "intent")
    combined_results.write_combined_json_report("combined_intent_report.json")

    changes = combined_results.show_labels_with_changes()
    changes = combined_results.sort_by_support(changes)
    metrics_order=["support", "f1-score", "precision","recall","confused_with"]
    changes = combined_results.order_metrics(changes, metrics_order=metrics_order)
    metrics_to_display=["support", "f1-score","confused_with"]
    table = NLUEvaluationResult.create_html_table(changes, columns=metrics_to_display)

    with open("formatted_results.html", "w+") as fh:
        fh.write(table)
