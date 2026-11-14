using Xunit;

namespace LegacyCsv.Tests;

public sealed class CsvParserTests
{
    [Fact]
    public void ParseLineHandlesQuotedCommasAndEscapedQuotes()
    {
        var fields = CsvParser.ParseLine("100,\"Acme, \"\"North\"\"\",42.50");
        Assert.Equal(3, fields.Count);
        Assert.Equal("100", fields[0]);
        Assert.Equal("Acme, \"North\"", fields[1]);
        Assert.Equal("42.50", fields[2]);
    }

    [Fact]
    public void SummarizeColumnTotalsDecimalValues()
    {
        var rows = new[]
        {
            "id,\"label\",amount",
            "1,\"Widget, A\",12.50",
            "2,\"Widget, B\",7.75"
        };

        var total = CsvParser.SummarizeColumn(rows.Skip(1), 2);
        Assert.Equal(20.25m, total);
    }
}
