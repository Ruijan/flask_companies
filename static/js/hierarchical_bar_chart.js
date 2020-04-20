// Initializing a class definition
class HierarchicalBarChart {
    constructor(container_name, data) {
        this.root = d3.hierarchy(data)
            .sort((a, b) => b.value - a.value)
            .eachAfter(d => d.index = d.parent ? d.parent.index = d.parent.index + 1 || 0 : 0)
        this.margin = ({top: 30, right: 30, bottom: 0, left: 200})
        this.barStep = 27
        this.barPadding = 3 / this.barStep
        this.duration = 500
        this.c_name = container_name
        this.container = d3.select(container_name)
        this.width = this.container.node().getBoundingClientRect().width - this.margin.right;
        this.height = getHeight(this.root, this.barStep, this.margin)
        this.container.style("height", (this.height + this.margin.bottom + this.margin.top)+"px");
        // create a tooltip
        this.tooltip = d3.select(this.c_name)
            .append("div")
            .style("opacity", 0)
            .attr("class", "tooltip")
            .style("position", "absolute")
            .style("background-color", "white")
            .style("border", "none")
            .style("padding", "5px")
            .style("width", "auto")
            .style("color", "black")

        this.color = d3.scaleOrdinal([true, false], ["steelblue", "#aaa"])
        this.x = d3.scaleLinear().range([this.margin.left, this.width - this.margin.right])
        this.x.domain([0, this.root.value]);
        this.buildSVG();
        down(this.svg, this.root, this);
    }

    buildSVG(){
        this.svg = this.container.append("svg")
            .attr("preserveAspectRatio", "xMinYMin meet")
            .attr("viewBox", "0 0 " + this.width + " " + this.height);
        this.svg.append("rect")
            .attr("class", "background")
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .attr("width", this.width)
            .attr("height", this.height)
            .attr("cursor", "pointer")
            .on("click", d => up(this.svg, d, this));
        this.xAxis = g => g
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.margin.top})`)
            .call(d3.axisTop(this.x).ticks(this.width / 80, "s"))
            .call(g => (g.selection ? g.selection() : g).select(".domain").remove())
        this.yAxis = g => g
            .attr("class", "y-axis")
            .attr("transform", `translate(${this.margin.left + 0.5},0)`)
            .call(g => g.append("line")
                .attr("stroke", "currentColor")
                .attr("y1", this.margin.top)
                .attr("y2", this.height - this.margin.bottom))
        this.svg.append("g")
            .call(this.xAxis);

        this.svg.append("g")
            .call(this.yAxis);

    }
}

function stagger(x, barStep) {
    let value = 0;
    return (d, i) => {
        const t = `translate(${x(value) - x(0)},${barStep * i})`;
        value += d.value;
        return t;
    };
}

function stack(i, x, barStep) {
    let value = 0;
    return d => {
        const t = `translate(${x(value) - x(0)},${barStep * i})`;
        value += d.value;
        return t;
    };
}


function getNumberOfChildren(n) {
    if (n.children == undefined) return 1;
    var nb_children = 0;
    n.children.forEach(function(c){
        nb_children += getNumberOfChildren(c);
    });
    return nb_children;
}

// Creates a set of bars for the given data node, at the specified index.
function createBar(svg, down, d, selector, chart) {
    const g = svg.insert("g", selector)
        .attr("class", "enter")
        .attr("transform", `translate(0,${chart.margin.top + chart.barStep * chart.barPadding})`)
        .attr("text-anchor", "end")
        .style("font", "14px sans-serif").style('fill', 'cornsilk');

    const bar = g.selectAll("g")
        .data(d.children)
        .join("g")
        .attr("cursor", d => !d.children ? null : "pointer")
        .on("click", d => down(svg, d, chart));

    bar.append("text")
        .attr("x", chart.margin.left - 6)
        .attr("y", chart.barStep * (1 - chart.barPadding) / 2)
        .attr("dy", ".35em")
        .text(d => d.data.name).style('fill', 'cornsilk');

    // Three function that change the tooltip when user hover / move / leave a cell
    let mouseover = function(d) {
        chart.tooltip.style("opacity", 1)
    }
    let mousemove = function(d) {
        let tip = ""
        if(d.children != undefined){
            tip = "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Companies</span>: </td>" +
                "<td style='text-align: right;'>" + getNumberOfChildren(d) + "</td></tr>" +
                "<tr><td style='text-align: center; padding-left: 5px; padding-right: 5px; color: dodgerblue;' colspan='2'>Click on the bar to expand</td></tr>"
        }
        chart.tooltip
            .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Name</span>: </td>" +
                "<td style='text-align: right;'>" + d.data.name + "</td></tr>" +
                "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Amount</span>: </td>" +
                "<td style='text-align: right;'>" + Math.round(d.value*100)/100 + "</td></tr>" +
                tip +
                "</table>")
            .style("top", (d3.event.pageY + 30)+"px")
            .style("left",(d3.event.pageX + 30)+"px")
    }
    let mouseleave = function(d) {
        chart.tooltip
            .style("opacity", 0)
    }

    bar.append("rect")
        .attr("x", chart.x(0))
        .attr("width", d => chart.x(d.value) - chart.x(0))
        .attr("height", chart.barStep * (1 - chart.barPadding))
        .on('mouseenter', function (actual, i) {
            d3.select(this).attr('opacity', 0.5)
            bar.selectAll('#limit').remove()
            const pos_x = chart.x(actual.value)
            bar.append('line')
                .attr('id', 'limit')
                .attr('x1', pos_x)
                .attr('y1', 0)
                .attr('x2', pos_x)
                .attr('y2', chart.barStep)
                .attr('stroke', 'red')
            bar.append('text')
                .attr('class', 'divergence')
                .attr('x', (a) => chart.x(a.value))
                .attr('y', (a) => chart.barStep * (1 - chart.barPadding) * 2 /3)
                .attr('fill', 'white')
                .attr('text-anchor', 'right')
                .text((a, idx) => {
                    const divergence = ((a.value - actual.value)/actual.value * 100).toFixed(1)
                    let text = ''
                    if (divergence > 0) text += '+'
                    text += `${divergence}%`
                    return idx !== i ? text : '';
                })
        })
        .on('mouseover', mouseover)
        .on('mouseleave', function (actual, i) {
            d3.select(this).attr('opacity', 1)
            bar.selectAll('#limit').remove()
            bar.selectAll('.divergence').remove()
            mouseleave(actual);
        })
        .on('mousemove',mousemove);

    return g;
}

function up(svg, d, chart) {
    if (!d.parent || !svg.selectAll(".exit").empty()) return;

    // Rebind the current node to the background.
    svg.select(".background").datum(d.parent);

    // Define two sequenced transitions.
    const transition1 = svg.transition().duration(chart.duration);
    const transition2 = transition1.transition();

    // Mark any currently-displayed bars as exiting.
    const exit = svg.selectAll(".enter")
        .attr("class", "exit");

    // Update the x-scale domain.
    chart.x.domain([0, d3.max(d.parent.children, d => d.value)]);

    // Update the x-axis.
    svg.selectAll(".x-axis").transition(transition1)
        .call(chart.xAxis);

    // Transition exiting bars to the new x-scale.
    exit.selectAll("g").transition(transition1)
        .attr("transform", stagger(chart.x, chart.barStep));

    // Transition exiting bars to the parent’s position.
    exit.selectAll("g").transition(transition2)
        .attr("transform", stack(d.index, chart.x, chart.barStep));

    // Transition exiting rects to the new scale and fade to parent color.
    exit.selectAll("rect").transition(transition1)
        .attr("width", d => chart.x(d.value) - chart.x(0))
        .attr("fill", chart.color(true));

    // Transition exiting text to fade out.
    // Remove exiting nodes.
    exit.transition(transition2)
        .attr("fill-opacity", 0)
        .remove();

    // Enter the new bars for the clicked-on data's parent.
    const enter = createBar(svg, down, d.parent, ".exit", chart)
        .attr("fill-opacity", 0);

    enter.selectAll("g")
        .attr("transform", (d, i) => `translate(0,${chart.barStep * i})`);

    // Transition entering bars to fade in over the full duration.
    enter.transition(transition2)
        .attr("fill-opacity", 1);

    // Color the bars as appropriate.
    // Exiting nodes will obscure the parent bar, so hide it.
    // Transition entering rects to the new x-scale.
    // When the entering parent rect is done, make it visible!
    enter.selectAll("rect")
        .attr("fill", d => chart.color(!!d.children))
        .attr("fill-opacity", p => p === d ? 0 : null)
        .transition(transition2)
        .attr("width", d => chart.x(d.value) - chart.x(0))
        .on("end", function(p) { d3.select(this).attr("fill-opacity", 1); });
}

function down(svg, d, chart) {
    if (!d.children || d3.active(svg.node())) return;

    // Rebind the current node to the background.
    svg.select(".background").datum(d);

    // Define two sequenced transitions.
    const transition1 = svg.transition().duration(chart.duration);
    const transition2 = transition1.transition();

    // Mark any currently-displayed bars as exiting.
    const exit = svg.selectAll(".enter")
        .attr("class", "exit");

    // Entering nodes immediately obscure the clicked-on bar, so hide it.
    exit.selectAll("rect")
        .attr("fill-opacity", p => p === d ? 0 : null);

    // Transition exiting bars to fade out.
    exit.transition(transition1)
        .attr("fill-opacity", 0)
        .remove();

    // Enter the new bars for the clicked-on data.
    // Per above, entering bars are immediately visible.
    const enter = createBar(svg, down, d, ".y-axis", chart)
        .attr("fill-opacity", 0);

    // Have the text fade-in, even though the bars are visible.
    enter.transition(transition1)
        .attr("fill-opacity", 1);

    // Transition entering bars to their new y-position.
    enter.selectAll("g")
        .attr("transform", stack(d.index, chart.x, chart.barStep))
        .transition(transition1)
        .attr("transform", stagger(chart.x, chart.barStep));

    // Update the x-scale domain.
    chart.x.domain([0, d3.max(d.children, d => d.value)]);

    // Update the x-axis.
    svg.selectAll(".x-axis").transition(transition2)
        .call(chart.xAxis);

    // Transition entering bars to the new x-scale.
    enter.selectAll("g").transition(transition2)
        .attr("transform", (d, i) => `translate(0,${chart.barStep * i})`);

    // Color the bars as parents; they will fade to children if appropriate.
    enter.selectAll("rect")
        .attr("fill", chart.color(true))
        .attr("fill-opacity", 1)
        .transition(transition2)
        .attr("fill", d => chart.color(!!d.children))
        .attr("width", d => chart.x(d.value) - chart.x(0));
}

function getHeight(root, barStep, margin){
    let max = 1;
    root.each(d => d.children && (max = Math.max(max, d.children.length)));
    return max * barStep + margin.top + margin.bottom;
}