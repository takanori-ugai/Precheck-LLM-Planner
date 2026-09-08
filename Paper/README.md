# 論文と公開補足資料

[APPENDIX.md](APPENDIX.md) に旧付録の内容をまとめています。プロンプト・知識変換コード、実験条件、全30表、全618件のデータ網羅表、実入力例をMarkdownで閲覧できます。

## 論文のビルド

pLaTeX、pBibTeX、dvipdfmx、latexmk と、本文で使用する LaTeX パッケージが必要です。
このディレクトリで次を実行してください。

```sh
latexmk main.tex
```

`latexmkrc` は pBibTeX による参考文献生成と、引用を解決するための pLaTeX の再実行を設定しています。
`fikes1971planex` と `fox2006stability` は `references.bib` に登録済みです。
これらの引用が未定義のまま残る場合は、古い補助ファイルと参考文献出力を再生成してください。

```sh
latexmk -gg main.tex
```

latexmk を使用しない場合は、次の順序で実行してください。

```sh
platex main.tex
pbibtex main
platex main.tex
platex main.tex
dvipdfmx main.dvi
```

Overleaf ではメイン文書を `main.tex` に設定し、`Recompile from scratch` を実行してください。
`JY1/hmc/b/n` などのフォント置換メッセージは、引用の未定義とは別の問題です。

## 論文の構成

`main.tex` は第1〜6章、謝辞、参考文献、著者紹介を組み立てます。付録は掲載しません。
前提条件・プロンプト・実入力例は第4章、実験設定・採点規則・主要な詳細結果は第5章に統合しました。
[公開補足資料](APPENDIX.md) に旧付録の詳細を掲載しています。`appendix-*.tex` は編集元のソースとして保存していますが、論文からは読み込みません。
全データ一覧、コード全文、個別ログなどの所在と移動内容は [構成変更の記録](revision-completion/Appendix-Removal.md) にまとめています。
