package pkg.iot_lab;

import com.anychart.APIlib;
import com.anychart.AnyChart;
import com.anychart.AnyChartView;
import com.anychart.chart.common.dataentry.DataEntry;
import com.anychart.chart.common.dataentry.ValueDataEntry;
import com.anychart.charts.Cartesian;
import com.anychart.core.cartesian.series.Line;
import com.anychart.data.Mapping;
import com.anychart.data.Set;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class ChartManager {
    private AnyChartView chartViewHumidity;
    private AnyChartView chartViewLight;
    private Cartesian cartesianHumidity;
    private Cartesian cartesianLight;
    private List<DataEntry> dataHumidity = new ArrayList<>();
    private List<DataEntry> dataLight = new ArrayList<>();
    private Set setHumidity;
    private Set setLight;

    public ChartManager(AnyChartView chartViewHumidity, AnyChartView chartViewLight) {
        this.chartViewHumidity = chartViewHumidity;
        this.chartViewLight = chartViewLight;
        initCharts();
    }

    private void initCharts() {
        initHumidityChart();
        initLightChart();
    }

    private void initHumidityChart() {
        APIlib.getInstance().setActiveAnyChartView(chartViewHumidity);
        cartesianHumidity = AnyChart.line();
        cartesianHumidity.title("Humidity History");
        dataHumidity.add(new ValueDataEntry("Start", 0));
        setHumidity = Set.instantiate();
        setHumidity.data(dataHumidity);
        Mapping seriesMapping1 = setHumidity.mapAs("{ x: 'x', value: 'value' }");
        Line series1 = cartesianHumidity.line(seriesMapping1);
        cartesianHumidity.yAxis(0).title("Humidity (%)");
        cartesianHumidity.xAxis(0).title("Time");
        chartViewHumidity.setChart(cartesianHumidity);
    }

    private void initLightChart() {
        APIlib.getInstance().setActiveAnyChartView(chartViewLight);
        cartesianLight = AnyChart.line();
        cartesianLight.title("Light Intensity");
        dataLight.add(new ValueDataEntry("Start", 0));
        setLight = Set.instantiate();
        setLight.data(dataLight);
        Mapping seriesMapping = setLight.mapAs("{ x: 'x', value: 'value' }");
        Line series = cartesianLight.line(seriesMapping);
        cartesianLight.yAxis(0).title("Light (lx)");
        cartesianLight.xAxis(0).title("Time");
        chartViewLight.setChart(cartesianLight);
    }

    public void updateHumidityChart(final double value) {
        chartViewHumidity.post(() -> {
            APIlib.getInstance().setActiveAnyChartView(chartViewHumidity);
            dataHumidity.add(new ValueDataEntry(getCurrentTimestamp(), value));
            setHumidity.data(dataHumidity);
            chartViewHumidity.invalidate();
        });
    }

    public void updateLightChart(final double value) {
        chartViewLight.post(() -> {
            APIlib.getInstance().setActiveAnyChartView(chartViewLight);
            dataLight.add(new ValueDataEntry(getCurrentTimestamp(), value));
            setLight.data(dataLight);
            chartViewLight.invalidate();
        });
    }
    private String getCurrentTimestamp() {
        SimpleDateFormat sdf = new SimpleDateFormat("HH:mm:ss", Locale.getDefault());
        return sdf.format(new Date());
    }
}
