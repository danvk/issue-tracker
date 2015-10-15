// JavaScript for the main stats page

function firstColumnToDate(row) { row[0] = new Date(row[0]); }

issues_by_day.forEach(firstColumnToDate);
pulls_by_day.forEach(firstColumnToDate);
stars_by_day.forEach(firstColumnToDate);

function extend(obj, new_attrs) {
  var out = {};
  for (var k in obj) {
    out[k] = obj[k];
  }
  for (var k in new_attrs) {
    out[k] = new_attrs[k];
  }
  return out;
}

function zeropad(x) { return (x < 10) ? '0' + x : x; }

var BASE_CHART_OPTIONS = {
  legend: 'always',
  labelsSeparateLines: true,
  includeZero: true,
  gridLineWidth: 0.1,
  axes: {
    x: {
      valueFormatter: function(millis) {
        var d = new Date(millis);
        return d.getFullYear() + '/' + zeropad(1 + d.getMonth()) + '/' + zeropad(d.getDate());
      }
    }
  }
};

var g_stars = new Dygraph('stars', stars_by_day,
    extend(BASE_CHART_OPTIONS, {
      labels: ['Date', 'Stargazers'],
      fillGraph: true
    }));

var g_open_issues = new Dygraph('issues', issues_by_day,
    extend(BASE_CHART_OPTIONS, {
      labels: ['Date', 'Open Issues'],
      fillGraph: true
    }));

var g_pulls = new Dygraph('pulls', pulls_by_day,
    extend(BASE_CHART_OPTIONS, {
      labels: ['Date', 'Open Pull Requests'],
      fillGraph: true
    }));

function labelUrl(label) {
  return 'https://github.com/' + owner + '/' + repo + '/labels/' + label;
}

$.getJSON(window.location + '/json?include_labels=True').then(function(data) {
  $('#labels-loading-message').hide();
  $('#labels-charts').show();

  var issues_by_label = data.by_label;
  issues_by_label.forEach(function(row, i) {
    if (i == 0) return;  // labels
    firstColumnToDate(row);
  });

  var g_labels = new Dygraph('labels', issues_by_label.slice(1),
      extend(BASE_CHART_OPTIONS, {
        labels: issues_by_label[0],
        labelsDiv: 'by-label-legend',
        highlightSeriesOpts: {
          strokeWidth: 2
        }
      }));

  var last_counts = issues_by_label[issues_by_label.length - 1];
  var count_labels = last_counts.slice(1).map(function(count, i) {
    var label = issues_by_label[0][i + 1];
    return [count, label];
  });
  var cells = _.sortBy(count_labels, function(x) { return -x[0]; })
      .map(function(x) {
        var count = x[0], label = x[1];
        var $row = $('<tr><td>' + count + '</td><td><a>' + label + '</a></td></tr>');
        $row.find('a').attr('href', labelUrl(label));
        return $row.get(0);
      });
  $('#current-labels table').append(cells);
});
