using System.Globalization;
using System.Text;

namespace LegacyCsv;

public static class CsvParser
{
    public static IReadOnlyList<string> ParseLine(string line)
    {
        if (line is null)
        {
            throw new ArgumentNullException(nameof(line));
        }

        var fields = new List<string>();
        var current = new StringBuilder();
        var inQuotes = false;

        for (var i = 0; i < line.Length; i++)
        {
            var ch = line[i];
            if (inQuotes)
            {
                if (ch == '"')
                {
                    if (i + 1 < line.Length && line[i + 1] == '"')
                    {
                        current.Append('"');
                        i++;
                    }
                    else
                    {
                        inQuotes = false;
                    }
                }
                else
                {
                    current.Append(ch);
                }
            }
            else if (ch == '"')
            {
                inQuotes = true;
            }
            else if (ch == ',')
            {
                fields.Add(current.ToString());
                current.Clear();
            }
            else
            {
                current.Append(ch);
            }
        }

        if (inQuotes)
        {
            throw new FormatException("Unterminated quoted CSV field");
        }

        fields.Add(current.ToString());
        return fields;
    }

    public static decimal SummarizeColumn(IEnumerable<string> lines, int columnIndex)
    {
        if (lines is null)
        {
            throw new ArgumentNullException(nameof(lines));
        }
        if (columnIndex < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(columnIndex));
        }

        decimal total = 0m;
        foreach (var line in lines)
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }
            var fields = ParseLine(line);
            if (columnIndex >= fields.Count)
            {
                throw new ArgumentOutOfRangeException(nameof(columnIndex));
            }
            total += decimal.Parse(fields[columnIndex].Trim(), CultureInfo.InvariantCulture);
        }
        return total;
    }
}
